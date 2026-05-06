"""Workflow / Agent registration and scripted forward path."""

from __future__ import annotations

import pytest

from rath.backend import get
from rath.flow.workflow import SingleAgent
from rath.llm import RathLLMAssistantMessage, RathLLMChatChoice, RathLLMChatResponse
from rath.session import Session, session_registry
from rath.session.chunk import ChunkKind
from tests.session.scripted_loop_provider import ScriptedSessionLoopProvider

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_active_session_registry() -> None:
    yield
    session_registry().set_active(None)


async def test_single_agent_registers_leaf_and_runs_scripted_loop() -> None:
    scripted = RathLLMChatResponse(
        id="wf1",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="from workflow"),
            ),
        ),
        created=9,
        model="scripted",
    )
    provider = ScriptedSessionLoopProvider([scripted])
    agent = SingleAgent("System prompt for workflow test.", provider)

    assert len(agent.named_agents()) == 1
    name, leaf = agent.named_agents()[0]
    assert name == "agent"
    assert leaf.provider is provider

    backend = get("local")
    async with await backend.open() as sandbox:
        user = Session.user_message("Trigger scripted reply.").with_sandbox(sandbox)
        out = await agent.forward_async(user)

    assert out.sandbox is sandbox
    assistant_chunks = [
        r.payload.get("content")
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.ASSISTANT
    ]
    assert any(c == "from workflow" for c in assistant_chunks)
