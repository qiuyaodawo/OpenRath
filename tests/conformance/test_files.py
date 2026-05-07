"""Filesystem-related :class:`~rath.backend.tool_types.BackendTool` calls per backend."""

from __future__ import annotations

import pytest

from rath.backend import (
    Backend,
    FileContent,
    FileEntries,
    FileWriteResult,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)

pytestmark = pytest.mark.anyio


async def test_write_then_read_text(backend: Backend) -> None:
    async with await backend.open() as sb:
        write = await sb.dispatch(
            BackendToolFilesWrite(path="hello.txt", data="hello")
        )
        assert isinstance(write, FileWriteResult)
        assert write.bytes_written == 5
        read = await sb.dispatch(BackendToolFilesRead(path="hello.txt"))
        assert isinstance(read, FileContent)
        assert read.data == "hello"


async def test_write_then_read_bytes(backend: Backend) -> None:
    payload = b"\x00\x01\x02binary\xffdata"
    async with await backend.open() as sb:
        await sb.dispatch(BackendToolFilesWrite(path="blob.bin", data=payload))
        result = await sb.dispatch(
            BackendToolFilesRead(path="blob.bin", encoding=None)
        )
        assert isinstance(result, FileContent)
        assert result.data == payload


async def test_exists_true_and_false(backend: Backend) -> None:
    async with await backend.open() as sb:
        await sb.dispatch(BackendToolFilesWrite(path="present.txt", data=""))
        assert (
            await sb.dispatch(BackendToolFilesExists(path="present.txt")) is True
        )
        assert await sb.dispatch(BackendToolFilesExists(path="nope.txt")) is False


async def test_list_returns_sorted_entries(backend: Backend) -> None:
    async with await backend.open() as sb:
        for name in ("c.txt", "a.txt", "b.txt"):
            await sb.dispatch(BackendToolFilesWrite(path=name, data=name))
        result = await sb.dispatch(BackendToolFilesList(path="."))
        assert isinstance(result, FileEntries)
        names = [e.name for e in result.entries]
        assert names == sorted(names)
        assert {"a.txt", "b.txt", "c.txt"}.issubset(set(names))


async def test_read_missing_path_raises(backend: Backend) -> None:
    async with await backend.open() as sb:
        with pytest.raises(FileNotFoundError):
            await sb.dispatch(BackendToolFilesRead(path="does-not-exist.txt"))


async def test_write_creates_parent_dirs(backend: Backend) -> None:
    async with await backend.open() as sb:
        await sb.dispatch(
            BackendToolFilesWrite(path="a/b/c/deep.txt", data="deep")
        )
        result = await sb.dispatch(BackendToolFilesRead(path="a/b/c/deep.txt"))
        assert isinstance(result, FileContent)
        assert result.data == "deep"
