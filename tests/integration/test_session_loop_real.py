"""Integration tests: live LLM chat + OpenSandbox.

Markers: ``integration``, ``live_llm``, ``opensandbox``.
"""

from __future__ import annotations

import os

import pytest

from rath.backend import preferred
from rath.flow.agent import Agent, AgentLLMProvider
from rath.flow.workflow import Workflow, run_session_loop_from_agent
from rath.llm import RathOpenAIChatClient
from rath.session import (
    ChunkKind,
    DefaultSessionLoopExecutor,
    Session,
    session_registry,
)
from rath.session.graph import LineageKind
from tests.conftest import opensandbox_real


def _openai_key_plausible() -> bool:
    return len(os.environ.get("OPENAI_API_KEY", "").strip()) >= 8


_needs_live_llm = pytest.mark.skipif(
    not _openai_key_plausible(),
    reason="OPENAI_API_KEY missing or too short (load .env via tests/conftest)",
)

pytestmark = [
    pytest.mark.anyio,
    opensandbox_real,
    _needs_live_llm,
    pytest.mark.opensandbox,
    pytest.mark.live_llm,
    pytest.mark.integration,
]


def _tool_rows_text(session: Session) -> str:
    parts: list[str] = []
    for row in session.chunk_table.rows:
        if row.kind != ChunkKind.TOOL_RESULT:
            continue
        parts.append(str(row.payload.get("content", "")))
    return "\n".join(parts)


async def test_run_session_loop_opensandbox_shell_echo() -> None:
    """Model issues ``run_shell_command``; stdout is recorded in tool chunks."""

    backend = preferred(["opensandbox"])
    client = RathOpenAIChatClient()
    executor = DefaultSessionLoopExecutor(client)
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None
    marker = "RATH_SESSION_E2E_ECHO_92653"
    agent = Agent(
        Session.from_system_prompt(
            "You are a test harness. Follow user instructions exactly. "
            "When the user asks you to run a shell command via a tool, call "
            "run_shell_command once with the cmd string they specify—no extra steps."
        ),
        AgentLLMProvider(model=model),
    )
    async with await backend.open() as sandbox:
        user = Session.user_message(
            f"Use run_shell_command exactly once. The cmd must run: echo {marker}"
        ).with_sandbox(sandbox)

        out = await run_session_loop_from_agent(
            user,
            agent,
            executor=executor,
            max_tool_rounds=12,
        )

        assert out.sandbox is sandbox
        assert out.sandbox.closed is False
        assert user.sandbox is None
        assert out.lineage is not None
        assert out.lineage.producer_user_session_id == user.id
        assert out.parent_session_ids == (user.id, agent.agent_session.id)
        assert out.lineage_kind == LineageKind.OP_SESSION_LOOP
        assert session_registry().get_active_id() == out.id

        tool_blob = _tool_rows_text(out)
        assert marker in tool_blob, tool_blob


class _ShellEchoWorkflow(Workflow):
    """Minimal workflow forwarding to :func:`run_session_loop`."""

    def __init__(
        self,
        system_prompt: str,
        executor: DefaultSessionLoopExecutor,
        model: str | None,
    ) -> None:
        super().__init__()
        self.actor = Agent(
            Session.from_system_prompt(system_prompt), AgentLLMProvider(model=model)
        )
        self._loop_executor = executor

    async def forward_async(self, session: Session) -> Session:
        return await run_session_loop_from_agent(
            session,
            self.actor,
            executor=self._loop_executor,
        )


async def test_workflow_opensandbox_shell_echo() -> None:
    """Same stack through :class:`Workflow.forward_async`."""

    backend = preferred(["opensandbox"])
    client = RathOpenAIChatClient()
    executor = DefaultSessionLoopExecutor(client)
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None
    marker = "RATH_SINGLE_AGENT_E2E_17402"
    system_prompt = (
        "You are a test harness. Use run_shell_command when the user asks "
        "for a shell command, exactly once with the cmd they describe."
    )
    async with await backend.open() as sandbox:
        user = Session.user_message(
            f"Call run_shell_command once with cmd: echo {marker}"
        ).with_sandbox(sandbox)

        wf = _ShellEchoWorkflow(system_prompt, executor, model)
        assert len(wf.named_agents()) == 1
        assert wf.named_agents()[0][0] == "actor"

        out = await wf.forward_async(user)

        assert out.sandbox is sandbox
        assert _tool_rows_text(out).count(marker) >= 1
