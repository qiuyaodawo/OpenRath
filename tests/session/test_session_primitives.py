"""Tests for ``rath.session.primitives`` lineage fields and Session methods."""

from __future__ import annotations

from rath.session.chunk import ChunkKind, ChunkTable
from rath.session import (
    LineageKind,
    create_leaf_system,
    create_leaf_user,
    detach_session,
    fork_session,
    merge_sessions,
)


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


def test_merge_concat_via_add() -> None:
    a = create_leaf_user("a")
    b = create_leaf_user("b")
    m = a + b
    assert len(m.chunk_table.rows) == 2
    assert m.parent_session_ids == (a.id, b.id)
    assert m.lineage_kind == LineageKind.OP_MERGE
    assert dict(m.lineage_extras).get("strategy") == "concat"

    def cat(tables: tuple[ChunkTable, ...]) -> ChunkTable:
        return ChunkTable(rows=tables[0].rows + tables[1].rows)

    m2 = merge_sessions((a, b), cat, strategy_name="concat")
    assert m2.chunk_table.rows == m.chunk_table.rows
