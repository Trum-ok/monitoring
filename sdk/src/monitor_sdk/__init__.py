import asyncio
import logging
import sys
import types

from .client import MonitorClient

logger = logging.getLogger("monitor_sdk")

_client: MonitorClient | None = None
_previous_excepthook = sys.excepthook
_previous_async_handler = None


def init(dsn: str, service_name: str = "default") -> None:
    """Initialize global SDK hooks for sync and async unhandled exceptions.

    Repeated calls are ignored: the SDK keeps the client and hooks from the
    first successful :func:`init`.

    Args:
        dsn: Monitor service ingest endpoint.
        service_name: Logical source service identifier.
    """

    global _client, _previous_async_handler
    if _client is not None:
        logger.warning("monitor_sdk.init() called more than once; ignoring")
        return

    _client = MonitorClient(dsn=dsn, service_name=service_name)
    sys.excepthook = _global_excepthook

    try:
        loop = asyncio.get_running_loop()
        _previous_async_handler = loop.get_exception_handler()
        loop.set_exception_handler(_async_exception_handler)
    except RuntimeError:
        # No running loop at init time; sync hook is still installed.
        _previous_async_handler = None


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
            _client.capture_exception(type(exc), exc, exc.__traceback__)
        else:
            _client.capture_message(str(context.get("message", "Unhandled asyncio exception")))

    if _previous_async_handler is not None:
        _previous_async_handler(loop, context)
    else:
        loop.default_exception_handler(context)
