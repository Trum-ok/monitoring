import types
import hashlib
import json
import threading
import traceback
from urllib.parse import urljoin
import requests


class MonitorClient:
    def __init__(self, dsn: str, service_name: str) -> None:
        """Create client instance.
        Args:
            dsn: Base URL of monitor-service (for example, ``http://localhost:8000``).
            service_name: Logical source service identifier used in local diagnostics.
        """
        self.dsn = dsn
        self.service_name = service_name

    def _generate_signature(self, exc_type: type[Exception], exc_tb: types.TracebackType | None) -> str:
        """Build stable hash from the deepest traceback frame.

        The signature source is ``filename:lineno:funcname`` from the last frame in traceback.
        If traceback is missing, fallback string uses exception type name.
        """
        if exc_tb is None:
            source = f"unknown:0:{exc_type.__name__}"
            return hashlib.sha256(source.encode("utf-8")).hexdigest()

        last_tb = exc_tb
        while last_tb.tb_next is not None:
            last_tb = last_tb.tb_next

        frame = last_tb.tb_frame
        filename = frame.f_code.co_filename
        lineno = last_tb.tb_lineno
        funcname = frame.f_code.co_name
        source = f"{filename}:{lineno}:{funcname}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _build_traceback_preview(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
        max_chars: int = 4000,
    ) -> str:
        rendered = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return rendered[:max_chars]

    def _ingest_url(self) -> str:
        base = self.dsn.rstrip("/") + "/"
        return urljoin(base, "api/errors")

    def _post_payload(self, payload: dict[str, str]) -> None:
        try:
            requests.post(self._ingest_url(), json=payload, timeout=2.0)
        except Exception:
            # Intentionally swallow SDK transport errors in crash path.
            return

    def capture_exception(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Capture and send exception event in fire-and-forget mode.

        Payload fields match monitor-service ingest schema:
        ``signature_hash``, ``exc_type``, ``message``, ``traceback_preview``.
        """
        signature_hash = self._generate_signature(exc_type, exc_tb)
        payload = {
            "signature_hash": signature_hash,
            "exc_type": exc_type.__name__,
            "message": str(exc_value),
            "traceback_preview": self._build_traceback_preview(exc_type, exc_value, exc_tb),
        }

        json.dumps(payload)
        thread = threading.Thread(target=self._post_payload, args=(payload,), daemon=True)
        thread.start()
