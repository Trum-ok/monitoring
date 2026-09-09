import atexit
import hashlib
import json
import logging
import queue
import threading
import time
import traceback
import types
from functools import cached_property
from urllib.parse import urljoin, urlsplit

import requests

logger = logging.getLogger("monitor_sdk")

ALLOWED_DSN_SCHEMES = frozenset({"http", "https"})
QUEUE_MAXSIZE = 100
FLUSH_TIMEOUT_SEC = 2.0


def validate_dsn(dsn: str) -> str:
    if not isinstance(dsn, str):
        raise TypeError(f"dsn must be a str, got {type(dsn).__name__}")

    value = dsn.strip()
    if not value:
        raise ValueError("dsn must be a non-empty string")

    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"dsn is not a valid URL: {value!r} ({exc})") from None

    if parts.scheme not in ALLOWED_DSN_SCHEMES:
        raise ValueError(
            f"dsn must use one of schemes {sorted(ALLOWED_DSN_SCHEMES)}, got {parts.scheme or None!r}: {value!r}"
        )

    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"dsn contains an invalid port: {value!r} ({exc})") from None

    if port is not None and not 1 <= port <= 65535:
        raise ValueError(f"dsn port must be in range 1-65535, got {port}: {value!r}")

    if not parts.hostname:
        raise ValueError(f"dsn must contain a host: {value!r}")

    if parts.query or parts.fragment:
        raise ValueError(f"dsn must not contain a query string or fragment: {value!r}")

    return value


class MonitorClient:
    def __init__(self, dsn: str, service_name: str, max_traceback_chars: int = 4000) -> None:
        """Create client instance.
        Args:
            dsn: Base URL of monitor-service (for example, ``http://localhost:8000``).
            service_name: Logical source service identifier; sent with every event and mixed into the error signature.
        """
        self.dsn = validate_dsn(dsn)
        self.service_name = service_name
        self.max_traceback_chars = max_traceback_chars
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._pending = 0
        self._pending_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._worker_lock = threading.Lock()

        atexit.register(self.flush)

    def _extract_signature_source(
        self, exc_type: type[Exception], exc_tb: types.TracebackType | None
    ) -> str:
        if exc_tb is None:
            return f"{self.service_name}:unknown:0:unknown:{exc_type.__name__}"

        last_tb = exc_tb
        while last_tb.tb_next is not None:
            last_tb = last_tb.tb_next

        frame = last_tb.tb_frame
        module = frame.f_globals.get("__name__") or frame.f_code.co_filename
        lineno = last_tb.tb_lineno
        funcname = frame.f_code.co_name
        return f"{self.service_name}:{module}:{lineno}:{funcname}:{exc_type.__name__}"

    def _generate_signature(
        self, exc_type: type[Exception], exc_tb: types.TracebackType | None
    ) -> str:
        source = self._extract_signature_source(exc_type, exc_tb)
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _build_traceback_preview(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> str:
        rendered = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return rendered[-self.max_traceback_chars :]

    @cached_property
    def _ingest_url(self) -> str:
        base = self.dsn.rstrip("/") + "/"
        return urljoin(base, "api/errors")

    def _post_payload(self, body: bytes) -> None:
        try:
            resp = requests.post(
                self._ingest_url,
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=2.0,
            )
            if resp.status_code >= 400:
                logger.warning("monitor ingest rejected: %s %s", resp.status_code, resp.text[:200])
        except Exception:
            logger.warning("monitor ingest failed", exc_info=True)

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return

        with self._worker_lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._worker_loop,
                    name="monitor-sdk-sender",
                    daemon=True,
                )
                self._worker.start()

    def _worker_loop(self) -> None:
        while True:
            body = self._queue.get()
            try:
                self._post_payload(body)
            finally:
                with self._pending_lock:
                    self._pending -= 1
                self._queue.task_done()

    def flush(self, timeout: float = FLUSH_TIMEOUT_SEC) -> None:
        """Block until queued events are sent or timeout expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._pending_lock:
                if self._pending == 0:
                    return

            time.sleep(0.05)

    def _send(self, payload: dict[str, str]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._ensure_worker()
        with self._pending_lock:
            self._pending += 1

        try:
            self._queue.put_nowait(body)
        except queue.Full:
            with self._pending_lock:
                self._pending -= 1
            logger.warning("monitor ingest queue full, dropping event")

    def capture_exception(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        signature_source = self._extract_signature_source(exc_type, exc_tb)
        signature_hash = self._generate_signature(exc_type, exc_tb)
        self._send(
            {
                "signature_hash": signature_hash,
                "signature_source": signature_source,
                "service_name": self.service_name,
                "exc_type": exc_type.__name__,
                "message": str(exc_value),
                "traceback_preview": self._build_traceback_preview(exc_type, exc_value, exc_tb),
            }
        )

    def capture_message(self, message: str) -> None:
        signature_source = f"{self.service_name}:message:{message[:200]}"
        signature_hash = hashlib.sha256(signature_source.encode("utf-8")).hexdigest()
        self._send(
            {
                "signature_hash": signature_hash,
                "signature_source": signature_source,
                "service_name": self.service_name,
                "exc_type": "Message",
                "message": message,
                "traceback_preview": "",
            }
        )
