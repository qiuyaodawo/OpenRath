"""Workflow base type: assigns :class:`~rath.flow.agent.Agent` members and runs sessions."""

from __future__ import annotations

import anyio

from typing import Any

from rath.flow.agent import Agent
from rath.session.session import Session


class Workflow:
    """Collects :class:`~rath.flow.agent.Agent` instances set as attributes and runs them."""

    __slots__ = ("_agents",)

    _agents: dict[str, Agent]

    def __init__(self) -> None:
        object.__setattr__(self, "_agents", {})

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Agent):
            agents: dict[str, Agent] = object.__getattribute__(self, "_agents")
            agents[name] = value
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        agents = object.__getattribute__(self, "_agents")
        agents.pop(name, None)
        super().__delattr__(name)

    def named_agents(self) -> tuple[tuple[str, Agent], ...]:
        """Agents registered via attribute assignment."""

        agents: dict[str, Agent] = object.__getattribute__(self, "_agents")
        return tuple(sorted(agents.items(), key=lambda x: x[0]))

    async def forward_async(self, session: Session) -> Session:
        """Subclasses orchestrate Sessions here."""
        raise NotImplementedError

    def forward(self, session: Session) -> Session:
        """Sync façade (``anyio.run``); safe only **without** a running loop."""

        return anyio.run(self.forward_async, session)

    def __call__(self, session: Session) -> Session:
        return self.forward(session)


__all__ = ["Workflow"]
