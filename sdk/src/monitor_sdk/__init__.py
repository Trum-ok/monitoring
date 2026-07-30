import asyncio
import logging
import sys
import threading
import types

from .client import MonitorClient

logger = logging.getLogger("monitor_sdk")

_client: MonitorClient | None = None
_previous_excepthook = sys.excepthook
_previous_threading_excepthook = threading.excepthook
_previous_async_handler = None
_asyncio_log_handler: logging.Handler | None = None


def init(dsn: str, service_name: str = "default") -> None:
    """Initialize global SDK hooks for sync, threading and async unhandled exceptions.

    Repeated calls are ignored: the SDK keeps the client and hooks from the
    first successful :func:`init`.

    When called outside a running asyncio loop, exceptions from asyncio tasks
    are captured via a fallback handler on the ``asyncio`` logger; call
    :func:`setup_asyncio` inside the loop for direct capture.

    Args:
        dsn: Monitor service ingest endpoint.
        service_name: Logical source service identifier.
    """

    global _client, _asyncio_log_handler
    if _client is not None:
        logger.warning("monitor_sdk.init() called more than once; ignoring")
        return

    _client = MonitorClient(dsn=dsn, service_name=service_name)
    sys.excepthook = _global_excepthook
    threading.excepthook = _threading_excepthook

    if _asyncio_log_handler is None:
        _asyncio_log_handler = _AsyncioLogHandler()
        logging.getLogger("asyncio").addHandler(_asyncio_log_handler)

    try:
        setup_asyncio()
    except RuntimeError:
        logger.info(
            "monitor_sdk.init() called outside a running asyncio loop; asyncio exceptions "
            "will be captured via the fallback log handler. Call monitor_sdk.setup_asyncio() "
            "inside the loop for direct capture."
        )


def setup_asyncio() -> None:
    """Install the SDK exception handler on the currently running event loop.

    Use when :func:`init` was called before the loop started: call this at the
    top of the async entrypoint. Repeated calls on the same loop are no-ops.

    Raises:
        RuntimeError: If there is no running event loop.
    """

    global _previous_async_handler
    loop = asyncio.get_running_loop()
    current = loop.get_exception_handler()
    if current is _async_exception_handler:
        return
    _previous_async_handler = current
    loop.set_exception_handler(_async_exception_handler)


def _mark_captured(exc: BaseException) -> None:
    try:
        exc._monitor_sdk_captured = True  # ty: ignore[unresolved-attribute]
    except Exception:
        pass


def _is_captured(exc: BaseException) -> bool:
    return bool(getattr(exc, "_monitor_sdk_captured", False))


class _AsyncioLogHandler(logging.Handler):
    """Fallback capture of unhandled asyncio exceptions logged by the default loop handler."""

    def emit(self, record: logging.LogRecord) -> None:
        if _client is None or record.exc_info is None:
            return
        exc_type, exc_value, exc_tb = record.exc_info
        if exc_type is None or exc_value is None:
            return
        if not issubclass(exc_type, Exception) or _is_captured(exc_value):
            return
        _client.capture_exception(exc_type, exc_value, exc_tb)


def _global_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: types.TracebackType | None,
) -> None:
    """Delegate unhandled synchronous exceptions to global monitor client.

    Wrapper should forward exception data to the client and optionally invoke
    original ``sys.excepthook`` to preserve default interpreter behavior.
    """

    if _client is not None and issubclass(exc_type, Exception):
        _client.capture_exception(exc_type, exc_value, exc_tb)
    _previous_excepthook(exc_type, exc_value, exc_tb)


def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
    if _client is not None and args.exc_value is not None and issubclass(args.exc_type, Exception):
        _client.capture_exception(args.exc_type, args.exc_value, args.exc_traceback)
    _previous_threading_excepthook(args)


def _async_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
    """Handle unhandled asyncio exceptions via global monitor client.

    Wrapper should extract exception metadata from asyncio ``context`` and forward
    it to the client in a non-blocking manner while preserving loop diagnostics.

    Args:
        loop: Event loop where exception occurred.
        context: Asyncio exception handler context mapping.
    """
    if _client is not None:
        exc = context.get("exception")
        if isinstance(exc, Exception):
            _mark_captured(exc)
            _client.capture_exception(type(exc), exc, exc.__traceback__)
        else:
            _client.capture_message(str(context.get("message", "Unhandled asyncio exception")))

    if _previous_async_handler is not None:
        _previous_async_handler(loop, context)
    else:
        loop.default_exception_handler(context)
