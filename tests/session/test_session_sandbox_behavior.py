"""Session sandbox binding and lifecycle (real LocalBackend, refcount-aware)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rath.backend import get
from rath.session import Session


def test_to_chainable_returns_self() -> None:
    s = Session.from_user_message("z")
    assert s.to("local") is s
    assert s.sandbox_backend == "local"


def test_with_session_optional_closes_handle() -> None:
    s = Session.from_user_message("y").to("local")
    assert s.sandbox is None
    with s:
        sb = s.require_sandbox()
        assert not sb.closed
        assert sb._refcount == 1
    assert s.sandbox is None
    assert sb.closed
    assert s.sandbox_backend == "local"


def test_require_sandbox_opens_lazily_and_keeps_one_reference() -> None:
    s = Session.from_user_message("x").to("local")
    sb = s.require_sandbox()
    try:
        assert sb._refcount == 1
        assert not sb.closed
        # require again is idempotent — no extra acquire.
        assert s.require_sandbox() is sb
        assert sb._refcount == 1
    finally:
        s.close_sandbox()
    assert sb.closed


def test_close_sandbox_releases_reference() -> None:
    s = Session.from_user_message("x").to("local")
    sb = s.require_sandbox()
    assert sb._refcount == 1
    s.close_sandbox()
    assert sb.closed
    assert s.sandbox is None


def test_bind_sandbox_acquires_and_releases_previous() -> None:
    backend = get("local")
    sb_a = backend.open()
    sb_b = backend.open()
    s = Session.from_user_message("x").bind_sandbox(sb_a)
    assert sb_a._refcount == 1
    assert sb_b._refcount == 0
    s.bind_sandbox(sb_b)
    # Old reference released → sb_a closed; new acquired → refcount 1.
    assert sb_a.closed
    assert sb_b._refcount == 1
    s.close_sandbox()
    assert sb_b.closed


def test_bind_same_sandbox_twice_is_noop() -> None:
    backend = get("local")
    sb = backend.open()
    s = Session.from_user_message("x").bind_sandbox(sb)
    assert sb._refcount == 1
    s.bind_sandbox(sb)
    assert sb._refcount == 1
    s.close_sandbox()
    assert sb.closed


def test_two_sessions_share_one_sandbox() -> None:
    backend = get("local")
    sb = backend.open()
    a = Session.from_user_message("a").bind_sandbox(sb)
    b = Session.from_user_message("b").bind_sandbox(sb)
    assert sb._refcount == 2
    a.close_sandbox()
    assert sb._refcount == 1
    assert not sb.closed
    b.close_sandbox()
    assert sb.closed


def test_require_sandbox_raises_after_backend_closed() -> None:
    backend = get("local")
    sandbox = backend.open()
    sandbox.acquire()
    user = Session.from_user_message("x").bind_sandbox(sandbox)
    assert user.require_sandbox() is sandbox
    # Drop our explicit acquire and the session's reference → refcount 0 → closed.
    sandbox.release()
    user.close_sandbox()
    assert sandbox.closed
    with pytest.raises(RuntimeError, match="session sandbox is closed"):
        user.sandbox = sandbox  # re-attach a closed handle to verify the check
        user.require_sandbox()


def test_to_accepts_str_spec_as_working_dir(tmp_path: Path) -> None:
    root = str(tmp_path.resolve())
    s = Session.from_user_message("w").to("local", spec=root)
    assert s._sandbox_open_spec is not None
    assert s._sandbox_open_spec.working_dir == root
    sb = s.require_sandbox()
    try:
        assert Path(sb.handle).resolve() == Path(root).resolve()
    finally:
        s.close_sandbox()
    assert Path(root).is_dir()


def test_to_closes_existing_handle_before_swap() -> None:
    s = Session.from_user_message("x").to("local")
    sb_old = s.require_sandbox()
    assert not sb_old.closed
    s.to("local")  # swap target → close current
    assert sb_old.closed
    assert s.sandbox is None
    assert s.sandbox_backend == "local"
