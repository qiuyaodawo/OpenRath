"""ContextVar-backed lineage recording (`session_graph_mode`, ``LineageRecorder``)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Generator
from uuid import UUID

from rath.session.graph.kind import LineageKind

_SESSION_GRAPH_MODE: ContextVar[bool] = ContextVar(
    "rath.session_graph_mode",
    default=True,
)


@dataclass(frozen=True, slots=True)
class LineageJournal:
    """Append-only visitation log (immutable).

    Mirrors a lightweight forward trace without standalone graph edge types.
    """

    visit_order: tuple[UUID, ...] = ()

    def append(self, session_id: UUID) -> LineageJournal:
        return LineageJournal(visit_order=self.visit_order + (session_id,))


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
) -> Generator[None, None, None]:
    """Attach ``LineageJournal`` (fresh by default); reset afterwards."""
    j = journal if journal is not None else LineageJournal()
    tok: Token[LineageJournal | None] = _LINEAGE_JOURNAL.set(j)
    try:
        yield None
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

        # Local import avoids ``Session`` at ``graph.recording`` import time.
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
            _LINEAGE_JOURNAL.set(lj.append(session.id))


__all__ = [
    "LineageJournal",
    "LineageRecorder",
    "lineage_journal_optional",
    "lineage_journal_tracking",
    "session_graph_mode",
    "session_graph_mode_override",
]
