"""Agent leaf object (Torch ``nn.Parameter`` analogy).

Holds configuration for one actor: ``system_session`` plus the
:class:`~rath.session.loop.SessionLoopProvider` implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from rath.session.loop import SessionLoopProvider
from rath.session.session import Session


@dataclass(slots=True)
class Agent:
    """Parameter-like bundle: system session + provider."""

    system_session: Session
    provider: SessionLoopProvider
