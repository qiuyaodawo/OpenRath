"""Session core: lineage primitives, Session.create member API, registry.

Consolidated from (preserves every test function name verbatim):
- test_session_primitives.py   (lineage primitives)
- test_session_member_api.py   (Session.create)
- test_session_registry.py     (SessionRegistry)
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from rath.session import (
    LineageKind,
    Session,
    create_leaf_user,
    detach_session,
    fork_session,
    session_registry,
)
from rath.session.chunk import ChunkKind


def test_create_leaf_user_sets_lineage_when_mode_on() -> None:
    s = create_leaf_user("hi")
    assert s.chunk_table.rows[-1].kind == ChunkKind.USER
    assert s.parent_session_ids == ()
    assert s.lineage_kind == LineageKind.LEAF_USER
    assert dict(s.lineage_extras).get("source") == "create_leaf_user"


def test_fork_preserves_rows_and_parents() -> None:
    base = create_leaf_user("x")
    f = base.fork()
    assert f.chunk_table.rows == base.chunk_table.rows
    assert f.parent_session_ids == (base.id,)
    assert f.lineage_kind == LineageKind.OP_FORK
    assert f.lineage_operator == "Session.fork"
    g = fork_session(base)
    assert g.parent_session_ids == (base.id,)


def test_detach_copies_chunks_without_graph_parents() -> None:
    base = create_leaf_user("u")
    d = base.detach()
    assert d.chunk_table.rows == base.chunk_table.rows
    assert d.parent_session_ids == ()
    assert d.lineage_kind == LineageKind.OP_DETACH
    assert d.lineage_operator == "Session.detach"
    e = detach_session(base)
    assert e.parent_session_ids == ()


def test_create_user_leaf_stamps_lineage_and_chunk() -> None:
    s = Session.create("user", "hello")
    assert len(s.chunk_table.rows) == 1
    row = s.chunk_table.rows[0]
    assert row.kind == ChunkKind.USER
    assert row.payload["content"] == "hello"
    assert s.parent_session_ids == ()
    assert s.lineage_kind is LineageKind.LEAF_USER
    assert s.lineage_operator == "Session.create"
    assert s.sandbox is None
    assert s.sandbox_backend is None


def test_create_system_leaf_stamps_lineage_and_chunk() -> None:
    s = Session.create("system", "you are helpful")
    assert len(s.chunk_table.rows) == 1
    row = s.chunk_table.rows[0]
    assert row.kind == ChunkKind.SYSTEM
    assert row.payload["content"] == "you are helpful"
    assert s.parent_session_ids == ()
    assert s.lineage_kind is LineageKind.LEAF_SYSTEM
    assert s.lineage_operator == "Session.create"


def test_create_empty_has_no_rows_and_no_lineage_stamp() -> None:
    s = Session.create("empty")
    assert s.chunk_table.rows == ()
    # "empty" intentionally skips LineageRecorder stamping; defaults remain.
    assert s.parent_session_ids == ()
    assert s.lineage_kind is LineageKind.UNKNOWN
    assert s.lineage_operator == "implicit"


def test_create_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown kind"):
        Session.create("agent", "no")


def test_create_then_to_chains_for_local_backend() -> None:
    s = Session.create("user", "hi").to("local")
    assert s.sandbox_backend == "local"
    assert s.sandbox is None
    with s:
        assert s.sandbox is not None
        assert not s.sandbox.closed
    assert s.sandbox is None


def test_session_registry_active_roundtrip() -> None:
    reg = session_registry()
    reg.set_active(None)

    s = Session.from_user_message("registry probe")
    reg.register(s)
    reg.set_active(s)
    assert reg.get_active_id() == s.id

    reg.set_active(None)
    assert reg.get_active_id() is None


def test_session_registry_get() -> None:
    reg = session_registry()
    s = Session.from_user_message("get probe")
    reg.register(s)
    assert reg.get(s.id) is s
    assert reg.get(uuid4()) is None
