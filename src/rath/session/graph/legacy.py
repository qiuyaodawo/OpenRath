"""Frozen DTO linking a loop output session to producer session ids (legacy surface)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionLineage:
    """Loop output lineage: ties ``out`` to producer user vs agent-system sessions.

    ``producer_system_session_id`` aligns with ``agent_session.id`` passed to
    :func:`~rath.session.loop.run_session_loop`.
    """

    producer_user_session_id: UUID
    producer_system_session_id: UUID
    operator: str = "run_session_loop"


__all__ = ["SessionLineage"]
