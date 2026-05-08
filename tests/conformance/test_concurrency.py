"""Concurrent sandboxes and post-close cleanup."""

from __future__ import annotations

import threading

import pytest

from rath.backend import (
    Backend,
    CommandResult,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesWrite,
)


def test_many_parallel_sandboxes(backend: Backend, python_cmd: list[str]) -> None:
    """Multiple sandboxes running in parallel must all finish and clean up."""

    n = 3
    errors: list[BaseException] = []
    lock = threading.Lock()

    def one_sandbox() -> None:
        try:
            with backend.open() as sb:
                result = sb.dispatch(
                    BackendToolCommandRun(cmd=[*python_cmd, "-c", "print(42)"])
                )
                assert isinstance(result, CommandResult)
                assert result.exit_code == 0
        except BaseException as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=one_sandbox) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert backend.sandbox_count() == 0


def test_two_sandboxes_independent(backend: Backend) -> None:
    """Work in one sandbox must not be visible in another."""
    s1 = backend.open()
    s2 = backend.open()
    try:
        s1.dispatch(BackendToolFilesWrite(path="only-in-s1.txt", data="x"))
        in_s1 = s1.dispatch(BackendToolFilesExists(path="only-in-s1.txt"))
        in_s2 = s2.dispatch(BackendToolFilesExists(path="only-in-s1.txt"))
        assert in_s1 is True
        assert in_s2 is False
    finally:
        backend.close(s1)
        backend.close(s2)
