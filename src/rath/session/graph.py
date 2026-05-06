"""Session lineage metadata from ``run_session_loop`` outputs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionLineage:
    """Producer sessions for graph-style bookkeeping (Torch autograd analogue)."""

    producer_user_session_id: UUID
    producer_system_session_id: UUID
    operator: str = "run_session_loop"
