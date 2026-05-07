"""Workflow base type: assigns ``Agent`` attributes and orchestrates sessions."""

from __future__ import annotations

import anyio

from typing import Any

from rath.flow.agent import Agent
from rath.flow.tool import ToolTable
from rath.session.loop import SessionLoopExecutor, run_session_loop
from rath.session.session import Session


class Workflow:
    """Collects attached ``Agent`` instances and subclasses run sessions here."""

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


async def run_session_loop_from_agent(
    user_session: Session,
    agent: Agent,
    *,
    executor: SessionLoopExecutor,
    tool_table: ToolTable | None = None,
    max_tool_rounds: int = 16,
) -> Session:
    """Maps ``Agent`` fields to ``run_session_loop`` keyword arguments."""
    return await run_session_loop(
        user_session,
        agent.agent_session,
        agent_provider=agent.provider,
        executor=executor,
        tool_table=tool_table,
        max_tool_rounds=max_tool_rounds,
    )


__all__ = ["Workflow", "run_session_loop_from_agent"]
