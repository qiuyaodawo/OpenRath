"""Stream and :class:`Event` semantics on each registered backend."""

from __future__ import annotations

import anyio
import pytest

from rath.backend import (
    Backend,
    CommandResult,
    FileContent,
    BackendToolCommandRun,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)

pytestmark = pytest.mark.anyio


async def test_fifo_within_one_stream(
    backend: Backend, python_cmd: list[str]
) -> None:
    """A dependency chain expressed via stream submission must be honoured."""
    async with await backend.open() as sb:
        async with sb.stream() as s:
            await s.submit(BackendToolFilesWrite(path="step.txt", data="a"))
            await s.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        (
                            "import pathlib;"
                            " pathlib.Path('step.txt').write_text("
                            " pathlib.Path('step.txt').read_text() + 'b')"
                        ),
                    ]
                )
            )
            f3 = await s.submit(BackendToolFilesRead(path="step.txt"))
            res = await f3
    assert isinstance(res, FileContent)
    assert res.data == "ab"


async def test_two_streams_progress_concurrently(
    backend: Backend, python_cmd: list[str]
) -> None:
    """Two streams over the same sandbox should overlap their work."""
    async with await backend.open() as sb:
        async with sb.stream() as s1, sb.stream() as s2:
            f1 = await s1.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(0.2); print('one')",
                    ]
                )
            )
            f2 = await s2.submit(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(0.2); print('two')",
                    ]
                )
            )
            with anyio.fail_after(5.0):
                r1 = await f1
                r2 = await f2

    assert isinstance(r1, CommandResult)
    assert isinstance(r2, CommandResult)
    assert b"one" in r1.stdout
    assert b"two" in r2.stdout


async def test_event_orders_across_streams(backend: Backend) -> None:
    """An event recorded on s1 must gate s2's subsequent submissions."""
    async with await backend.open() as sb:
        async with sb.stream() as s1, sb.stream() as s2:
            await s1.submit(BackendToolFilesWrite(path="ordered.txt", data="hello"))
            evt = await s1.record_event()
            await s2.wait_event(evt)
            f = await s2.submit(BackendToolFilesRead(path="ordered.txt"))
            res = await f
    assert isinstance(res, FileContent)
    assert res.data == "hello"


async def test_synchronize_drains_stream(backend: Backend) -> None:
    async with await backend.open() as sb:
        async with sb.stream() as s:
            for i in range(3):
                await s.submit(BackendToolFilesWrite(path=f"f{i}.txt", data=str(i)))
            await s.synchronize()
            for i in range(3):
                f = await s.submit(BackendToolFilesRead(path=f"f{i}.txt"))
                res = await f
                assert isinstance(res, FileContent)
                assert res.data == str(i)
