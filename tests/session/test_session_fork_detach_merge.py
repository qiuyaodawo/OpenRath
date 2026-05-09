"""Session.fork / detach / __add__ and sandbox handle lifecycle."""

from __future__ import annotations

from rath.backend import get
from rath.session import Session, create_leaf_user


def test_fork_does_not_steal_open_sandbox_handle() -> None:
    backend = get("local")
    with backend.open() as sb:
        s = Session.from_user_message("hi").with_sandbox(sb)
        assert s.require_sandbox() is sb
        f = s.fork()
        assert s.sandbox is sb
        assert not sb.closed
        assert f.sandbox is None
        assert f.sandbox_backend == "local"


def test_fork_inherits_backend_target_without_open_handle() -> None:
    s = Session.from_user_message("x").to("local", spec=".")
    f = s.fork()
    assert s.sandbox is None
    assert f.sandbox is None
    assert f.sandbox_backend == "local"


def test_detach_same_as_fork_for_sandbox_fields() -> None:
    s = create_leaf_user("y").to("local")
    d = s.detach()
    assert d.sandbox is None
    assert d.sandbox_backend == "local"


def test_add_merge_has_no_handle_and_left_backend_wins() -> None:
    a = Session.from_user_message("left").to("local", spec=".")
    b = Session.from_user_message("right")
    m = a + b
    assert m.sandbox is None
    assert m.sandbox_backend == "local"
    assert m._sandbox_open_spec is not None


def test_add_with_invalid_type_returns_not_implemented() -> None:
    s = create_leaf_user("z")
    assert s.__add__(1) is NotImplemented  # type: ignore[arg-type]


def test_fork_session_wraps_session_fork() -> None:
    from rath.session.primitives import fork_session

    base = create_leaf_user("w")
    f1 = base.fork()
    f2 = fork_session(base)
    assert f1.chunk_table.rows == f2.chunk_table.rows
    assert f1.parent_session_ids == f2.parent_session_ids


def test_associative_concat_row_order() -> None:
    a = create_leaf_user("1")
    b = create_leaf_user("2")
    c = create_leaf_user("3")
    m1 = (a + b) + c
    m2 = a + (b + c)
    assert len(m1.chunk_table.rows) == len(m2.chunk_table.rows) == 3
    assert [r.payload.get("content") for r in m1.chunk_table.rows] == [
        "1",
        "2",
        "3",
    ]
    assert [r.payload.get("content") for r in m2.chunk_table.rows] == [
        "1",
        "2",
        "3",
    ]
