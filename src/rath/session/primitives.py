"""Session construction primitives.

Lineage stamping goes through :class:`~rath.session.graph.LineageRecorder` and is a
no-op when :func:`~rath.session.graph.session_graph_mode` is false.

:class:`~rath.session.session.Session` methods :meth:`~rath.session.session.Session.fork`
and :meth:`~rath.session.session.Session.detach` duplicate
:attr:`~rath.session.session.Session.chunk_table` only; open sandbox handles are never
copied. Module-level :func:`fork_session` / :func:`detach_session` delegate to those
methods.
"""

from __future__ import annotations

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


__all__ = [
    "create_leaf_system",
    "create_leaf_user",
    "detach_session",
    "fork_session",
]
