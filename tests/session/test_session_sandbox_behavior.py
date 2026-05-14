"""Session sandbox binding and lifecycle (real LocalBackend)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rath.backend import get
from rath.session import Session


def test_take_sandbox_raises_when_no_backend_and_no_handle() -> None:
    user = Session.from_user_message("x")

    assert user.sandbox is None

    with pytest.raises(RuntimeError, match="no sandbox to take"):
        user.take_sandbox()


def test_take_sandbox_lazy_opens_when_backend_is_local() -> None:
    user = Session.from_user_message("x").to("local")

    assert user.sandbox is None

    sb = user.take_sandbox()

    assert user.sandbox is None

    assert sb.backend.name == "local"

    sb.backend.close(sb)


def test_with_session_optional_closes_handle() -> None:
    s = Session.from_user_message("y").to("local")

    assert s.sandbox is None

    with s:
        sb = s.require_sandbox()

        assert not sb.closed

    assert s.sandbox is None

    assert sb.closed

    assert s.sandbox_backend == "local"


def test_to_chainable_returns_self() -> None:
    s = Session.from_user_message("z")

    assert s.to("local") is s

    assert s.sandbox_backend == "local"


def test_take_sandbox_detaches_then_can_rebind() -> None:
    backend = get("local")

    with backend.open() as sb:
        user = Session.from_user_message("x").with_sandbox(sb)

        assert user.take_sandbox() is sb

        assert user.sandbox is None

        user.bind_sandbox(sb)

        assert user.require_sandbox() is sb


def test_require_sandbox_raises_after_backend_closed() -> None:
    backend = get("local")
    sandbox = backend.open()

    try:
        user = Session.from_user_message("x").with_sandbox(sandbox)

        assert user.require_sandbox() is sandbox
    finally:
        backend.close(sandbox)

    assert sandbox.closed is True

    with pytest.raises(RuntimeError, match="session sandbox is closed"):
        user.require_sandbox()


def test_to_accepts_str_spec_as_working_dir(tmp_path: Path) -> None:
    root = str(tmp_path.resolve())
    s = Session.from_user_message("w").to("local", spec=root)
    assert s._sandbox_open_spec is not None
    assert s._sandbox_open_spec.working_dir == root
    sb = s.take_sandbox()
    try:
        assert Path(sb.handle).resolve() == Path(root).resolve()
    finally:
        sb.backend.close(sb)
    assert Path(root).is_dir()
