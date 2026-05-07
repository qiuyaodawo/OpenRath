"""Session construction primitives.

Lineage stamping goes through :class:`~rath.session.graph.LineageRecorder` and is a
no-op when :func:`~rath.session.graph.session_graph_mode` is false.

``fork_session`` / ``detach_session`` / ``split_session`` share the same sandbox rule:
they duplicate :attr:`~rath.session.session.Session.chunk_table` only (new sessions
leave ``sandbox`` unset so callers can bind explicitly).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from rath.session.chunk import ChunkTable
from rath.session.graph import LineageKind, LineageRecorder
from rath.session.session import Session


def create_leaf_user(text: str) -> Session:
    """Leaf user transcript; stamps ``LEAF_USER`` when lineage mode is on."""

    s = Session.user_message(text)
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=(),
        lineage_operator="create_leaf_user",
        lineage_kind=LineageKind.LEAF_USER,
        lineage_extras=(("source", "create_leaf_user"),),
    )
    return s


def create_leaf_system(prompt: str) -> Session:
    """Leaf system transcript; stamps ``LEAF_SYSTEM`` when lineage mode is on."""

    s = Session.from_system_prompt(prompt)
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=(),
        lineage_operator="create_leaf_system",
        lineage_kind=LineageKind.LEAF_SYSTEM,
        lineage_extras=(("source", "create_leaf_system"),),
    )
    return s


def fork_session(from_session: Session) -> Session:
    """Copy rows to a fresh session (**no** sandbox); parent is ``from_session``."""

    rows = tuple(from_session.chunk_table.rows)
    forked = Session(chunk_table=ChunkTable(rows=rows))
    LineageRecorder.stamp_new_session(
        forked,
        parent_session_ids=(from_session.id,),
        lineage_operator="fork_session",
        lineage_kind=LineageKind.OP_FORK,
    )
    return forked


def detach_session(from_session: Session) -> Session:
    """Fork transcript with empty ``parent_session_ids`` (fresh graph root).

    Does not copy ``sandbox``; bind explicitly if needed.
    """

    rows = tuple(from_session.chunk_table.rows)
    detached = Session(chunk_table=ChunkTable(rows=rows))
    LineageRecorder.stamp_new_session(
        detached,
        parent_session_ids=(),
        lineage_operator="detach_session",
        lineage_kind=LineageKind.OP_DETACH,
        lineage_extras=(),
    )
    return detached


def split_session(parent: Session) -> tuple[Session, Session]:
    """Two children sharing ``parent``'s rows; differentiated via ``branch`` extras."""

    rows = tuple(parent.chunk_table.rows)
    left = Session(chunk_table=ChunkTable(rows=rows))
    right = Session(chunk_table=ChunkTable(rows=rows))
    LineageRecorder.stamp_new_session(
        left,
        parent_session_ids=(parent.id,),
        lineage_operator="split_session",
        lineage_kind=LineageKind.OP_SPLIT_CHILD,
        lineage_extras=(("branch", "left"),),
    )
    LineageRecorder.stamp_new_session(
        right,
        parent_session_ids=(parent.id,),
        lineage_operator="split_session",
        lineage_kind=LineageKind.OP_SPLIT_CHILD,
        lineage_extras=(("branch", "right"),),
    )
    return left, right


def merge_sessions(
    parents_ordered: Sequence[Session],
    rows_merge_policy: Callable[[Sequence[ChunkTable]], ChunkTable],
    *,
    strategy_name: str = "custom",
) -> Session:
    """Merge transcripts with ``rows_merge_policy``; parent order fixes fan-in."""

    tables = tuple(p.chunk_table for p in parents_ordered)
    merged = Session(chunk_table=rows_merge_policy(tables))
    LineageRecorder.stamp_new_session(
        merged,
        parent_session_ids=tuple(p.id for p in parents_ordered),
        lineage_operator="merge_sessions",
        lineage_kind=LineageKind.OP_MERGE,
        lineage_extras=(("strategy", strategy_name),),
    )
    return merged


__all__ = [
    "create_leaf_system",
    "create_leaf_user",
    "detach_session",
    "fork_session",
    "merge_sessions",
    "split_session",
]
