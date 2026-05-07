"""Tests for ``rath.session.primitives`` lineage fields."""

from __future__ import annotations

from rath.session.chunk import ChunkKind, ChunkTable
from rath.session import (
    LineageKind,
    create_leaf_system,
    create_leaf_user,
    detach_session,
    fork_session,
    merge_sessions,
    split_session,
)


def test_create_leaf_user_sets_lineage_when_mode_on() -> None:
    s = create_leaf_user("hi")
    assert s.chunk_table.rows[-1].kind == ChunkKind.USER
    assert s.parent_session_ids == ()
    assert s.lineage_kind == LineageKind.LEAF_USER
    assert dict(s.lineage_extras).get("source") == "create_leaf_user"


def test_fork_preserves_rows_and_parents() -> None:
    base = create_leaf_user("x")
    f = fork_session(base)
    assert f.chunk_table.rows == base.chunk_table.rows
    assert f.parent_session_ids == (base.id,)
    assert f.lineage_kind == LineageKind.OP_FORK


def test_split_carries_branch_extras() -> None:
    p = create_leaf_system("prompt")
    left, right = split_session(p)
    assert left.chunk_table.rows == right.chunk_table.rows == p.chunk_table.rows
    assert left.parent_session_ids == (p.id,)
    assert right.parent_session_ids == (p.id,)
    assert dict(left.lineage_extras)["branch"] == "left"
    assert dict(right.lineage_extras)["branch"] == "right"


def test_detach_copies_chunks_without_graph_parents() -> None:
    base = create_leaf_user("u")
    d = detach_session(base)
    assert d.chunk_table.rows == base.chunk_table.rows
    assert d.parent_session_ids == ()
    assert d.lineage_kind == LineageKind.OP_DETACH
    assert d.lineage_extras == ()


def test_merge_concat_policy() -> None:
    a = create_leaf_user("a")
    b = create_leaf_user("b")

    def cat(tables: tuple[ChunkTable, ...]) -> ChunkTable:
        return ChunkTable(rows=tables[0].rows + tables[1].rows)

    m = merge_sessions((a, b), cat, strategy_name="concat")
    assert len(m.chunk_table.rows) == 2
    assert m.parent_session_ids == (a.id, b.id)
    assert m.lineage_kind == LineageKind.OP_MERGE
    assert dict(m.lineage_extras)["strategy"] == "concat"
