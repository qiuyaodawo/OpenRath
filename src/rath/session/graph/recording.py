"""ContextVar-backed lineage recording (`session_graph_mode`, ``LineageRecorder``)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Generator
from uuid import UUID

from rath.session.graph.kind import LineageKind

_SESSION_GRAPH_MODE: ContextVar[bool] = ContextVar(
    "rath.session_graph_mode",
    default=True,
)


@dataclass(slots=True)
class LineageJournal:
    """Append-only visitation log mutated in place.

    Ordered session ids visited in this run; edges are not materialized.

    Mutable on purpose so that callers can read ``visit_order`` after the
    :func:`lineage_journal_tracking` context manager exits. Use
    :meth:`record` from primitives that stamp lineage; do not mutate
    ``visit_order`` directly.
    """

    visit_order: list[UUID] = field(default_factory=list)

    def record(self, session_id: UUID) -> None:
        """Append ``session_id`` to ``visit_order`` in place."""
        self.visit_order.append(session_id)

    def append(self, session_id: UUID) -> LineageJournal:
        """Deprecated: returns ``self`` after :meth:`record` for legacy callers.

        Earlier versions returned a fresh instance, which silently dropped
        updates when used through the ContextVar. New code should call
        :meth:`record` directly.
        """
        self.visit_order.append(session_id)
        return self


_LINEAGE_JOURNAL: ContextVar[LineageJournal | None] = ContextVar(
    "rath.lineage_journal",
    default=None,
)


def session_graph_mode() -> bool:
    """Return whether primitives / loop should stamp lineage."""
    try:
        return _SESSION_GRAPH_MODE.get()
    except LookupError:
        return True


@contextmanager
def session_graph_mode_override(enabled: bool) -> Generator[None, None, None]:
    """Temporarily toggle lineage stamping (tokens restored on exit)."""
    tok: Token[bool] = _SESSION_GRAPH_MODE.set(enabled)
    try:
        yield None
    finally:
        _SESSION_GRAPH_MODE.reset(tok)


def lineage_journal_optional() -> LineageJournal | None:
    """Current journal attachment, if any (``None`` = disabled)."""
    try:
        return _LINEAGE_JOURNAL.get()
    except LookupError:
        return None


@contextmanager
def lineage_journal_tracking(
    *,
    journal: LineageJournal | None = None,
) -> Generator[LineageJournal, None, None]:
    """Attach a :class:`LineageJournal` for this block and yield it.

    The yielded journal is mutated in place by :meth:`LineageRecorder.stamp_new_session`
    as new sessions are created inside the block; ``visit_order`` is readable
    after the context manager exits.

    Existing callers that wrote ``with lineage_journal_tracking():`` still
    work because the yielded value can be discarded.
    """
    j = journal if journal is not None else LineageJournal()
    tok: Token[LineageJournal | None] = _LINEAGE_JOURNAL.set(j)
    try:
        yield j
    finally:
        _LINEAGE_JOURNAL.reset(tok)


class LineageRecorder:
    """Writes flat lineage attributes on ``Session`` when graph mode is enabled."""

    @staticmethod
    def stamp_new_session(
        session: object,
        *,
        parent_session_ids: tuple[UUID, ...],
        lineage_operator: str,
        lineage_kind: LineageKind,
        lineage_extras: tuple[tuple[str, Any], ...] = (),
    ) -> None:
        """No-op if ``session_graph_mode()`` is false. Skips ``chunk_table``."""

        # Import locally so ``graph.recording`` does not depend on ``Session`` at import time.
        from rath.session.session import Session

        if not isinstance(session, Session):
            raise TypeError(f"expected Session, got {type(session)!r}")
        if not session_graph_mode():
            return
        session.parent_session_ids = parent_session_ids
        session.lineage_operator = lineage_operator
        session.lineage_kind = lineage_kind
        session.lineage_extras = lineage_extras
        lj = lineage_journal_optional()
        if lj is not None:
            lj.record(session.id)


__all__ = [
    "LineageJournal",
    "LineageRecorder",
    "lineage_journal_optional",
    "lineage_journal_tracking",
    "session_graph_mode",
    "session_graph_mode_override",
]
