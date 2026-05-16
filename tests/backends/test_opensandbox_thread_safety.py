"""Regression tests for ``OpenSandboxBackend.close`` thread-safety.

These tests do **not** require a reachable opensandbox server: they build
the backend, inject a fake native handle into ``_natives`` by hand, and
race ``close()`` from multiple threads. The point is to exercise the
``_natives_lock`` check-and-pop, not the real I/O path that follows it.
"""

from __future__ import annotations

import threading
from typing import Any
from unittest.mock import MagicMock

from rath.backend.abc import BackendSandbox
from rath.backend.opensandbox import OpenSandboxBackend


def _fake_native(name: str = "fake") -> Any:
    """Async-mock native object whose kill()/close() are awaitable no-ops."""

    async def _noop() -> None:
        return None

    n = MagicMock(name=name)
    n.id = name
    n.kill = MagicMock(side_effect=lambda: _noop())
    n.close = MagicMock(side_effect=lambda: _noop())
    return n


def test_concurrent_close_calls_native_close_exactly_once() -> None:
    """Two threads calling ``backend.close(sb)`` on the same sandbox must
    result in the native's close coroutine being scheduled exactly once.

    The lock pattern protects the check-and-pop sequence; the second
    thread to acquire the lock must observe ``sandbox.closed=True`` and
    return without re-popping or re-scheduling close.
    """
    backend = OpenSandboxBackend()
    native = _fake_native("handle-1")
    backend._natives[native.id] = native
    sandbox = BackendSandbox(backend=backend, handle=native.id, spec=None)

    # Replace the runner so close() doesn't actually drive an event loop;
    # we only need to count how many times the close coroutine is
    # scheduled.
    runner = MagicMock()

    def _run(coro: Any) -> None:
        # Close the coroutine so Python doesn't warn about it being unawaited.
        coro.close()
        return None

    runner.run = MagicMock(side_effect=_run)
    backend._runner = runner

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def _race() -> None:
        try:
            barrier.wait(timeout=2.0)
            backend.close(sandbox)
        except BaseException as exc:  # noqa: BLE001 -- collected for assertion
            errors.append(exc)

    threads = [threading.Thread(target=_race) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)
        assert not t.is_alive(), "close() thread did not finish in time"

    assert not errors, f"close() raised in worker thread(s): {errors!r}"
    assert sandbox.closed is True
    assert native.id not in backend._natives
    # The runner.run side wraps a coroutine; the count of invocations is
    # what proves "close coroutine scheduled exactly once".
    assert runner.run.call_count == 1, (
        f"native close should be scheduled exactly once, got "
        f"{runner.run.call_count} call(s)"
    )


def test_close_after_close_is_noop_same_thread() -> None:
    """Single-threaded sanity: double close on the same sandbox is a no-op."""
    backend = OpenSandboxBackend()
    native = _fake_native("handle-2")
    backend._natives[native.id] = native
    sandbox = BackendSandbox(backend=backend, handle=native.id, spec=None)
    runner = MagicMock()

    def _run(coro: Any) -> None:
        # Close the coroutine so Python doesn't warn about it being unawaited.
        coro.close()
        return None

    runner.run = MagicMock(side_effect=_run)
    backend._runner = runner

    backend.close(sandbox)
    backend.close(sandbox)

    assert sandbox.closed is True
    assert runner.run.call_count == 1
