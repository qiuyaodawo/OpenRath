"""Workflow / Agent registration and scripted forward path."""

from __future__ import annotations

import pytest

from rath.backend import get
from rath.flow.agent import Agent, AgentLLMProvider
from rath.flow.workflow import Workflow, run_session_loop_from_agent
from rath.llm import RathLLMAssistantMessage, RathLLMChatChoice, RathLLMChatResponse
from rath.session import Session, session_registry
from rath.session.chunk import ChunkKind
from tests.session.scripted_loop_executor import ScriptedSessionLoopExecutor

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clear_active_session_registry() -> None:
    yield
    session_registry().set_active(None)


class _ScriptedEchoWorkflow(Workflow):
    def __init__(self, scripted: RathLLMChatResponse) -> None:
        super().__init__()
        self._exec = ScriptedSessionLoopExecutor([scripted])
        self.agent = Agent(
            Session.from_system_prompt("System prompt for workflow test."),
            AgentLLMProvider(),
        )

    async def forward_async(self, session: Session) -> Session:
        return await run_session_loop_from_agent(
            session,
            self.agent,
            executor=self._exec,
        )


async def test_workflow_registers_agent_and_runs_loop() -> None:
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
    wf = _ScriptedEchoWorkflow(scripted)

    assert len(wf.named_agents()) == 1
    name, leaf = wf.named_agents()[0]
    assert name == "agent"
    assert isinstance(leaf, Agent)
    assert isinstance(leaf.provider, AgentLLMProvider)

    backend = get("local")
    async with await backend.open() as sandbox:
        user = Session.user_message("Trigger scripted reply.").with_sandbox(sandbox)
        out = await wf.forward_async(user)

    assert out.sandbox is sandbox
    assistant_chunks = [
        r.payload.get("content")
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.ASSISTANT
    ]
    assert any(c == "from workflow" for c in assistant_chunks)
