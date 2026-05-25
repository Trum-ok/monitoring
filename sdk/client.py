import types
import hashlib


class MonitorClient:
    def __init__(self, dsn: str, service_name: str) -> None:
        """Create client instance.

        Args:
            dsn: Target monitor-service ingest URL.
            service_name: Logical source service name included into payload route field.
        """
        self.dsn = dsn
        self.service_name = service_name

    def _generate_signature(self, exc_type: type[Exception], exc_tb: types.TracebackType | None) -> str:
        ...

    def capture_exception(
        self,
        exc_type: type[Exception],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        ...
