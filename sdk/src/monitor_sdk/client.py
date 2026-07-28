import hashlib
import json
import threading
import traceback
import types
from urllib.parse import urljoin
from functools import cached_property

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
        max_chars: int = 4000,
    ) -> str:
        rendered = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        return rendered[:max_chars]

    @cached_property
    def _ingest_url(self) -> str:
        base = self.dsn.rstrip("/") + "/"
        return urljoin(base, "api/errors")

    def _post_payload(self, body: bytes) -> None:
        try:
            requests.post(
                self._ingest_url,
                data=body,
                headers={"Content-Type": "application/json"},
                timeout=2.0,
            )
        except Exception:
            return

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
        thread = threading.Thread(target=self._post_payload, args=(body,), daemon=True)
        thread.start()
