"""End-to-end session loop: live LLM + OpenSandbox (no mocks).

These tests require ``opensandbox-server`` on ``localhost:8080`` and
``OPENAI_API_KEY`` (see project ``.env``). They are marked ``integration``,
``opensandbox``, and ``live_llm`` for selective runs.
"""

from __future__ import annotations

import os

import pytest

from rath.backend import preferred
from rath.flow.workflow import SingleAgent
from rath.llm import RathOpenAIChatClient
from rath.session import (
    ChunkKind,
    DefaultSessionLoopProvider,
    Session,
    run_session_loop,
    session_registry,
)
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
    provider = DefaultSessionLoopProvider(client)
    marker = "RATH_SESSION_E2E_ECHO_92653"
    system = Session.from_system_prompt(
        "You are a test harness. Follow user instructions exactly. "
        "When the user asks you to run a shell command via a tool, call "
        "run_shell_command once with the cmd string they specify—no extra steps."
    )
    async with await backend.open() as sandbox:
        user = Session.user_message(
            f"Use run_shell_command exactly once. The cmd must run: echo {marker}"
        ).with_sandbox(sandbox)

        out = await run_session_loop(user, system, provider, max_tool_rounds=12)

        assert out.sandbox is sandbox
        assert out.sandbox.closed is False
        assert user.sandbox is None
        assert out.lineage is not None
        assert out.lineage.producer_user_session_id == user.id
        assert session_registry().get_active_id() == out.id

        tool_blob = _tool_rows_text(out)
        assert marker in tool_blob, tool_blob


async def test_single_agent_workflow_opensandbox_shell_echo() -> None:
    """Same stack through :class:`SingleAgent` async forward."""

    backend = preferred(["opensandbox"])
    client = RathOpenAIChatClient()
    provider = DefaultSessionLoopProvider(client)
    marker = "RATH_SINGLE_AGENT_E2E_17402"
    system_prompt = (
        "You are a test harness. Use run_shell_command when the user asks "
        "for a shell command, exactly once with the cmd they describe."
    )
    async with await backend.open() as sandbox:
        user = Session.user_message(
            f"Call run_shell_command once with cmd: echo {marker}"
        ).with_sandbox(sandbox)

        agent = SingleAgent(system_prompt, provider)
        assert len(agent.named_agents()) == 1

        out = await agent.forward_async(user)

        assert out.sandbox is sandbox
        assert _tool_rows_text(out).count(marker) >= 1
