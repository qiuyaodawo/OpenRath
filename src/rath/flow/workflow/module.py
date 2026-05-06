"""Composable workflow modules — Torch ``nn.Module`` analogy."""

from __future__ import annotations

import anyio

from typing import Any

from rath.flow.agent import Agent
from rath.session.loop import SessionLoopProvider, run_session_loop
from rath.session.session import Session


class Workflow:
    """Base class registering :class:`~rath.flow.agent.Agent` children."""

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


class SingleAgent(Workflow):
    """One-Agent workflow wrapping :func:`~rath.session.loop.run_session_loop`."""

    __slots__ = ("agent",)

    def __init__(self, system_prompt: str, provider: SessionLoopProvider) -> None:
        super().__init__()
        self.agent = Agent(Session.from_system_prompt(system_prompt), provider)

    async def forward_async(self, session: Session) -> Session:
        return await run_session_loop(
            session,
            self.agent.system_session,
            self.agent.provider,
        )


__all__ = ["Workflow", "SingleAgent"]
