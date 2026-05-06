"""Session sandbox binding and lifecycle (real LocalBackend)."""

from __future__ import annotations

import pytest

from rath.backend import get
from rath.session import Session

pytestmark = pytest.mark.anyio


async def test_take_sandbox_raises_when_missing() -> None:
    user = Session.user_message("x")
    assert user.sandbox is None
    with pytest.raises(RuntimeError, match="no sandbox to take"):
        user.take_sandbox()


async def test_take_sandbox_detaches_then_can_rebind() -> None:
    backend = get("local")
    async with await backend.open() as sb:
        user = Session.user_message("x").with_sandbox(sb)
        assert user.take_sandbox() is sb
        assert user.sandbox is None
        user.bind_sandbox(sb)
        assert user.require_sandbox() is sb


async def test_require_sandbox_raises_after_backend_closed() -> None:
    backend = get("local")
    sandbox = await backend.open()
    try:
        user = Session.user_message("x").with_sandbox(sandbox)
        assert user.require_sandbox() is sandbox
    finally:
        await backend.close(sandbox)
    assert sandbox.closed is True
    with pytest.raises(RuntimeError, match="session has no active sandbox"):
        user.require_sandbox()
