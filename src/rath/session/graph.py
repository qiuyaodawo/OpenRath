"""Session lineage metadata from ``run_session_loop`` outputs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SessionLineage:
    """Links a loop output session to the producer user/system session ids."""

    producer_user_session_id: UUID
    producer_system_session_id: UUID
    operator: str = "run_session_loop"
