import hashlib
import json
import threading
import traceback
import types
import logging
from urllib.parse import urljoin, urlsplit
from functools import cached_property

import requests

logger = logging.getLogger("monitor_sdk")

ALLOWED_DSN_SCHEMES = frozenset({"http", "https"})


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
            service_name: Logical source service identifier used in local diagnostics.
        """
        self.dsn = validate_dsn(dsn)
        self.service_name = service_name
        self.max_traceback_chars = max_traceback_chars

    def _extract_signature_source(self, exc_type: type[Exception], exc_tb: types.TracebackType | None) -> str:
        if exc_tb is None:
            return f"unknown:0:{exc_type.__name__}"

        last_tb = exc_tb
        while last_tb.tb_next is not None:
            last_tb = last_tb.tb_next

        frame = last_tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = last_tb.tb_lineno
        funcname = frame.f_code.co_name
        return f"{filename}:{lineno}:{funcname}"

    def _generate_signature(self, exc_type: type[Exception], exc_tb: types.TracebackType | None) -> str:
        source = self._extract_signature_source(exc_type, exc_tb)
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _build_traceback_preview(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> str:
        rendered = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return rendered[-self.max_traceback_chars:]

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

    def capture_exception(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        signature_source = self._extract_signature_source(exc_type, exc_tb)
        signature_hash = self._generate_signature(exc_type, exc_tb)
        payload = {
            "signature_hash": signature_hash,
            "signature_source": signature_source,
            "exc_type": exc_type.__name__,
            "message": str(exc_value),
            "traceback_preview": self._build_traceback_preview(exc_type, exc_value, exc_tb),
        }

        body = json.dumps(payload).encode("utf-8")
        thread = threading.Thread(target=self._post_payload, args=(body,), daemon=False)
        thread.start()
