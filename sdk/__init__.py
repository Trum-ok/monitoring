"""Public SDK initialization API for global exception hooks."""

from __future__ import annotations

import asyncio
import sys
import types

from .client import MonitorClient

_client: MonitorClient | None = None
_previous_excepthook = sys.excepthook


def init(dsn: str, service_name: str = "default") -> None:
    """Initialize global SDK hooks for sync and async unhandled exceptions.

    This function should:
    1. Create and store a global :class:`MonitorClient` instance.
    2. Replace ``sys.excepthook`` with :func:`_global_excepthook` wrapper.
    3. Attach :func:`_async_exception_handler` to current running event loop
       (or loops created later by integration glue).

    Args:
        dsn: Monitor service ingest endpoint.
        service_name: Logical source service identifier.
    """

    ...


def _global_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: types.TracebackType | None,
) -> None:
    """Delegate unhandled synchronous exceptions to global monitor client.

    Wrapper should forward exception data to the client and optionally invoke
    original ``sys.excepthook`` to preserve default interpreter behavior.
    """

    ...


def _async_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
    """Handle unhandled asyncio exceptions via global monitor client.

    Wrapper should extract exception metadata from asyncio ``context`` and forward
    it to the client in a non-blocking manner while preserving loop diagnostics.

    Args:
        loop: Event loop where exception occurred.
        context: Asyncio exception handler context mapping.
    """

    ...
