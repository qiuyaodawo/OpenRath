"""Sandbox open/close, async context manager, and ``sandbox_count``."""

from __future__ import annotations

import pytest

from rath.backend import Backend, BackendSandboxClosed, BackendToolCommandRun

pytestmark = pytest.mark.anyio


async def test_open_returns_unclosed_sandbox(backend: Backend) -> None:
    sb = await backend.open()
    try:
        assert sb.closed is False
    finally:
        await backend.close(sb)


async def test_close_marks_sandbox_closed(backend: Backend) -> None:
    sb = await backend.open()
    await backend.close(sb)
    assert sb.closed is True


async def test_async_with_auto_closes(backend: Backend) -> None:
    async with await backend.open() as sb:
        assert sb.closed is False
    assert sb.closed is True


async def test_double_close_is_idempotent(backend: Backend) -> None:
    sb = await backend.open()
    await backend.close(sb)
    await backend.close(sb)
    assert sb.closed is True


async def test_dispatch_after_close_raises(
    backend: Backend, python_cmd: list[str]
) -> None:
    sb = await backend.open()
    await backend.close(sb)
    with pytest.raises(BackendSandboxClosed):
        await sb.dispatch(BackendToolCommandRun(cmd=[*python_cmd, "-c", "pass"]))


async def test_sandbox_count_tracks_open_sandboxes(backend: Backend) -> None:
    assert backend.sandbox_count() == 0
    s1 = await backend.open()
    assert backend.sandbox_count() == 1
    s2 = await backend.open()
    assert backend.sandbox_count() == 2
    await backend.close(s1)
    assert backend.sandbox_count() == 1
    await backend.close(s2)
    assert backend.sandbox_count() == 0
