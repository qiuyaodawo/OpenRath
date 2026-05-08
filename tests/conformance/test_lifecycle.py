"""Sandbox open/close, context manager, and ``sandbox_count``."""

from __future__ import annotations

import pytest

from rath.backend import Backend, BackendSandboxClosed, BackendToolCommandRun


def test_open_returns_unclosed_sandbox(backend: Backend) -> None:
    sb = backend.open()
    try:
        assert sb.closed is False
    finally:
        backend.close(sb)


def test_close_marks_sandbox_closed(backend: Backend) -> None:
    sb = backend.open()
    backend.close(sb)
    assert sb.closed is True


def test_context_manager_auto_closes(backend: Backend) -> None:
    with backend.open() as sb:
        assert sb.closed is False
    assert sb.closed is True


def test_double_close_is_idempotent(backend: Backend) -> None:
    sb = backend.open()
    backend.close(sb)
    backend.close(sb)
    assert sb.closed is True


def test_dispatch_after_close_raises(backend: Backend, python_cmd: list[str]) -> None:
    sb = backend.open()
    backend.close(sb)
    with pytest.raises(BackendSandboxClosed):
        sb.dispatch(BackendToolCommandRun(cmd=[*python_cmd, "-c", "pass"]))


def test_sandbox_count_tracks_open_sandboxes(backend: Backend) -> None:
    assert backend.sandbox_count() == 0
    s1 = backend.open()
    assert backend.sandbox_count() == 1
    s2 = backend.open()
    assert backend.sandbox_count() == 2
    backend.close(s1)
    assert backend.sandbox_count() == 1
    backend.close(s2)
    assert backend.sandbox_count() == 0
