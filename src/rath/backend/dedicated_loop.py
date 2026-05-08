"""Single background event loop for async-only SDK clients (OpenSandbox).

Exposes blocking :meth:`DedicatedEventLoopThread.run` for synchronous call sites while
keeping one long-lived loop for connection state bound to async httpx / OpenSandbox.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")


class DedicatedEventLoopThread:
    """Thread hosting ``asyncio`` loop; :meth:`run` blocks the caller until completion."""

    __slots__ = ("_loop", "_ready", "_thread")

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

        def _runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            loop.run_forever()

        self._thread = threading.Thread(
            target=_runner,
            daemon=True,
            name="rath-asyncio-backend",
        )
        self._thread.start()
        if not self._ready.wait(timeout=60.0):
            raise RuntimeError("background asyncio loop failed to start")
        if self._loop is None:
            raise RuntimeError("asyncio loop is unset")

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        loop = self._loop
        assert loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, loop)
        return fut.result()


_OPENSANDBOX_ASYNC: DedicatedEventLoopThread | None = None
_OPENSANDBOX_LOCK = threading.Lock()


def shared_opensandbox_loop() -> DedicatedEventLoopThread:
    """Process-wide dedicated loop for OpenSandbox async SDK usage."""

    global _OPENSANDBOX_ASYNC
    with _OPENSANDBOX_LOCK:
        if _OPENSANDBOX_ASYNC is None:
            _OPENSANDBOX_ASYNC = DedicatedEventLoopThread()
        return _OPENSANDBOX_ASYNC
