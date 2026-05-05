"""Conformance: concurrent sandbox usage and cleanup invariants."""

from __future__ import annotations

import anyio
import pytest

from rath.backend import Backend, CommandResult, CommandRun


pytestmark = pytest.mark.anyio


async def test_many_parallel_sandboxes(
    backend: Backend, python_cmd: list[str]
) -> None:
    """Multiple sandboxes running in parallel must all finish and clean up.

    The default count is small (3) so the test stays fast on backends with
    multi-second sandbox creation cost (e.g. OpenSandbox's container start).
    """
    n = 3

    async def one_sandbox() -> None:
        async with await backend.open() as sb:
            result = await sb.dispatch(
                CommandRun(cmd=[*python_cmd, "-c", "print(42)"])
            )
            assert isinstance(result, CommandResult)
            assert result.exit_code == 0

    async with anyio.create_task_group() as tg:
        for _ in range(n):
            tg.start_soon(one_sandbox)

    assert backend.sandbox_count() == 0


async def test_two_sandboxes_independent(backend: Backend) -> None:
    """Work in one sandbox must not be visible in another."""
    s1 = await backend.open()
    s2 = await backend.open()
    try:
        from rath.backend import FilesExists, FilesWrite

        await s1.dispatch(FilesWrite(path="only-in-s1.txt", data="x"))
        in_s1 = await s1.dispatch(FilesExists(path="only-in-s1.txt"))
        in_s2 = await s2.dispatch(FilesExists(path="only-in-s1.txt"))
        assert in_s1 is True
        assert in_s2 is False
    finally:
        await backend.close(s1)
        await backend.close(s2)
