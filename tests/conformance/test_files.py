"""Filesystem-related :class:`~rath.backend.tool_types.BackendTool` calls per backend."""

from __future__ import annotations

from rath.backend import (
    Backend,
    FileContent,
    FileEntries,
    FileWriteResult,
    ToolExecutionFailure,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)


def test_write_then_read_text(backend: Backend) -> None:
    with backend.open() as sb:
        write = sb.dispatch(BackendToolFilesWrite(path="hello.txt", data="hello"))
        assert isinstance(write, FileWriteResult)
        assert write.bytes_written == 5
        read = sb.dispatch(BackendToolFilesRead(path="hello.txt"))
        assert isinstance(read, FileContent)
        assert read.data == "hello"


def test_write_then_read_bytes(backend: Backend) -> None:
    payload = b"\x00\x01\x02binary\xffdata"
    with backend.open() as sb:
        sb.dispatch(BackendToolFilesWrite(path="blob.bin", data=payload))
        result = sb.dispatch(
            BackendToolFilesRead(path="blob.bin", encoding=None)
        )
        assert isinstance(result, FileContent)
        assert result.data == payload


def test_exists_true_and_false(backend: Backend) -> None:
    with backend.open() as sb:
        sb.dispatch(BackendToolFilesWrite(path="present.txt", data=""))
        assert sb.dispatch(BackendToolFilesExists(path="present.txt")) is True
        assert sb.dispatch(BackendToolFilesExists(path="nope.txt")) is False


def test_list_returns_sorted_entries(backend: Backend) -> None:
    with backend.open() as sb:
        for name in ("c.txt", "a.txt", "b.txt"):
            sb.dispatch(BackendToolFilesWrite(path=name, data=name))
        result = sb.dispatch(BackendToolFilesList(path="."))
        assert isinstance(result, FileEntries)
        names = [e.name for e in result.entries]
        assert names == sorted(names)
        assert {"a.txt", "b.txt", "c.txt"}.issubset(set(names))


def test_read_missing_path_returns_failure(backend: Backend) -> None:
    with backend.open() as sb:
        r = sb.dispatch(BackendToolFilesRead(path="does-not-exist.txt"))
        assert isinstance(r, ToolExecutionFailure)
        assert r.kind == "file_not_found"


def test_write_creates_parent_dirs(backend: Backend) -> None:
    with backend.open() as sb:
        sb.dispatch(BackendToolFilesWrite(path="a/b/c/deep.txt", data="deep"))
        result = sb.dispatch(BackendToolFilesRead(path="a/b/c/deep.txt"))
        assert isinstance(result, FileContent)
        assert result.data == "deep"
