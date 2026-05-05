"""Conformance: Stream / Event semantics across all backends."""

from __future__ import annotations

import sys

import anyio
import pytest

from rath.backend import (
    Backend,
    CommandResult,
    CommandRun,
    FileContent,
    FilesRead,
    FilesWrite,
)

pytestmark = pytest.mark.anyio


async def test_fifo_within_one_stream(backend: Backend) -> None:
    """A dependency chain expressed via stream submission must be honoured."""
    async with await backend.open() as sb:
        async with sb.stream() as s:
            await s.submit(FilesWrite(path="step.txt", data="a"))
            await s.submit(
                CommandRun(
                    cmd=[
                        sys.executable,
                        "-c",
                        (
                            "import pathlib;"
                            " pathlib.Path('step.txt').write_text("
                            " pathlib.Path('step.txt').read_text() + 'b')"
                        ),
                    ]
                )
            )
            f3 = await s.submit(FilesRead(path="step.txt"))
            res = await f3
    assert isinstance(res, FileContent)
    assert res.data == "ab"


async def test_two_streams_progress_concurrently(backend: Backend) -> None:
    """Two streams over the same sandbox should overlap their work."""
    async with await backend.open() as sb:
        async with sb.stream() as s1, sb.stream() as s2:
            f1 = await s1.submit(
                CommandRun(
                    cmd=[
                        sys.executable,
                        "-c",
                        "import time; time.sleep(0.2); print('one')",
                    ]
                )
            )
            f2 = await s2.submit(
                CommandRun(
                    cmd=[
                        sys.executable,
                        "-c",
                        "import time; time.sleep(0.2); print('two')",
                    ]
                )
            )
            with anyio.fail_after(1.0):
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
            await s1.submit(FilesWrite(path="ordered.txt", data="hello"))
            evt = await s1.record_event()
            await s2.wait_event(evt)
            f = await s2.submit(FilesRead(path="ordered.txt"))
            res = await f
    assert isinstance(res, FileContent)
    assert res.data == "hello"


async def test_synchronize_drains_stream(backend: Backend) -> None:
    async with await backend.open() as sb:
        async with sb.stream() as s:
            for i in range(3):
                await s.submit(FilesWrite(path=f"f{i}.txt", data=str(i)))
            await s.synchronize()
            for i in range(3):
                f = await s.submit(FilesRead(path=f"f{i}.txt"))
                res = await f
                assert isinstance(res, FileContent)
                assert res.data == str(i)
