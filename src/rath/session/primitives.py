"""Session construction primitives.

Lineage stamping goes through :class:`~rath.session.graph.LineageRecorder` and is a
no-op when :func:`~rath.session.graph.session_graph_mode` is false.

:class:`~rath.session.session.Session` methods :meth:`~rath.session.session.Session.fork`,
:meth:`~rath.session.session.Session.detach`, and :meth:`~rath.session.session.Session.__add__`
duplicate :attr:`~rath.session.session.Session.chunk_table` only; open sandbox handles
are never copied. Module-level :func:`fork_session` / :func:`detach_session` delegate to
those methods. :func:`merge_sessions` supports N-way merges with a custom row policy;
binary concat-merge is ``session_left + session_right``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from rath.session.chunk import ChunkTable
from rath.session.graph import LineageKind, LineageRecorder
from rath.session.session import Session


def create_leaf_user(text: str) -> Session:
    """Leaf user transcript; stamps ``LEAF_USER`` when lineage mode is on."""

    s = Session.from_user_message(text)
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

    s = Session.from_agent_prompt(prompt)
    LineageRecorder.stamp_new_session(
        s,
        parent_session_ids=(),
        lineage_operator="create_leaf_system",
        lineage_kind=LineageKind.LEAF_SYSTEM,
        lineage_extras=(("source", "create_leaf_system"),),
    )
    return s


def fork_session(from_session: Session) -> Session:
    """Same as :meth:`~rath.session.session.Session.fork`."""

    return from_session.fork()


def detach_session(from_session: Session) -> Session:
    """Same as :meth:`~rath.session.session.Session.detach`."""

    return from_session.detach()


def merge_sessions(
    parents_ordered: Sequence[Session],
    rows_merge_policy: Callable[[Sequence[ChunkTable]], ChunkTable],
    *,
    strategy_name: str = "custom",
) -> Session:
    """Merge transcripts with ``rows_merge_policy``; parent order fixes fan-in.

    For two sessions with simple row concatenation, prefer ``left + right`` instead.
    """

    tables = tuple(p.chunk_table for p in parents_ordered)
    if parents_ordered:
        p0 = parents_ordered[0]
        sb0 = p0.sandbox_backend
        spec0 = p0._sandbox_open_spec
    else:
        sb0 = None
        spec0 = None
    merged = Session(
        chunk_table=rows_merge_policy(tables),
        sandbox_backend=sb0,
        _sandbox_open_spec=spec0,
    )
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
]
