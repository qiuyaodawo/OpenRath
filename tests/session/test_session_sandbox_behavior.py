"""Session sandbox binding and lifecycle (real LocalBackend)."""



from __future__ import annotations



import pytest



from rath.backend import get

from rath.session import Session





def test_take_sandbox_raises_when_no_backend_and_no_handle() -> None:

    user = Session.user_message("x", sandbox_backend=None)

    assert user.sandbox is None

    with pytest.raises(RuntimeError, match="no sandbox to take"):

        user.take_sandbox()





def test_take_sandbox_lazy_opens_when_backend_is_local() -> None:

    user = Session.user_message("x")

    assert user.sandbox is None

    sb = user.take_sandbox()

    assert user.sandbox is None

    assert sb.backend.name == "local"

    sb.backend.close(sb)





def test_with_session_optional_closes_handle() -> None:

    s = Session.user_message("y")

    assert s.sandbox is None

    with s:

        sb = s.require_sandbox()

        assert not sb.closed

    assert s.sandbox is None

    assert sb.closed

    assert s.sandbox_backend == "local"





def test_to_chainable_returns_self() -> None:

    s = Session.user_message("z")

    assert s.to("local") is s

    assert s.sandbox_backend == "local"





def test_take_sandbox_detaches_then_can_rebind() -> None:

    backend = get("local")

    with backend.open() as sb:

        user = Session.user_message("x").with_sandbox(sb)

        assert user.take_sandbox() is sb

        assert user.sandbox is None

        user.bind_sandbox(sb)

        assert user.require_sandbox() is sb





def test_require_sandbox_raises_after_backend_closed() -> None:

    backend = get("local")

    sandbox = backend.open()

    try:

        user = Session.user_message("x").with_sandbox(sandbox)

        assert user.require_sandbox() is sandbox

    finally:

        backend.close(sandbox)

    assert sandbox.closed is True

    with pytest.raises(RuntimeError, match="session sandbox is closed"):

        user.require_sandbox()


