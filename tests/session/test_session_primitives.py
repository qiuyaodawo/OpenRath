"""Tests for ``rath.session.primitives`` lineage fields and Session methods."""

from __future__ import annotations

from rath.session import (
    LineageKind,
    create_user_session,
    detach_session,
    fork_session,
)
from rath.session.chunk import ChunkKind


def test_create_user_session_sets_lineage_when_mode_on() -> None:
    s = create_user_session("hi")
    assert s.chunk_table.rows[-1].kind == ChunkKind.USER
    assert s.parent_session_ids == ()
    assert s.lineage_kind == LineageKind.LEAF_USER
    assert dict(s.lineage_extras).get("source") == "create_user_session"


def test_fork_preserves_rows_and_parents() -> None:
    base = create_user_session("x")
    f = base.fork()
    assert f.chunk_table.rows == base.chunk_table.rows
    assert f.parent_session_ids == (base.id,)
    assert f.lineage_kind == LineageKind.OP_FORK
    assert f.lineage_operator == "Session.fork"
    g = fork_session(base)
    assert g.parent_session_ids == (base.id,)


def test_detach_copies_chunks_without_graph_parents() -> None:
    base = create_user_session("u")
    d = base.detach()
    assert d.chunk_table.rows == base.chunk_table.rows
    assert d.parent_session_ids == ()
    assert d.lineage_kind == LineageKind.OP_DETACH
    assert d.lineage_operator == "Session.detach"
    e = detach_session(base)
    assert e.parent_session_ids == ()
