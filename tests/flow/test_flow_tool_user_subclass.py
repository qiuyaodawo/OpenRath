"""User-defined :class:`~rath.flow.tool.FlowToolCall` in ``run_session_loop``."""

from __future__ import annotations

import json

import pytest

from rath.backend import get
from rath.flow.agent_param import AgentParam, Provider
from rath.flow.tool import FlowToolCall
from rath.llm import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.session import Session, run_session_loop, session_registry
from rath.session.chunk import ChunkKind
from tests.session.scripted_loop_executor import ScriptedSessionLoopExecutor


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    yield
    session_registry().set_active(None)


class AddOneTool(FlowToolCall):
    @property
    def name(self) -> str:
        return "add_one"

    @property
    def description(self) -> str | None:
        return "Add 1 to x"

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
            "additionalProperties": False,
        }

    def __call__(self, session: Session, arguments: dict[str, object]) -> int:
        return int(arguments["x"]) + 1


def test_user_flow_tool_result_in_tool_chunk() -> None:
    body = {"x": 41}
    part = RathLLMToolCallPart(
        id="a1",
        type="function",
        function=RathLLMToolCallFunction(
            name="add_one",
            arguments=json.dumps(body),
            arguments_parsed=body,
            arguments_parse_error=False,
        ),
    )
    first = RathLLMChatResponse(
        id="t1",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="tool_calls",
                message=RathLLMAssistantMessage(tool_calls=(part,)),
            ),
        ),
        created=1,
        model="script",
    )
    second = RathLLMChatResponse(
        id="t2",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="ok"),
            ),
        ),
        created=2,
        model="script",
    )
    executor = ScriptedSessionLoopExecutor([first, second])
    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("go").bind_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            tools=[AddOneTool()],
            executor=executor,
        )

    tool_rows = [r for r in out.chunk_table.rows if r.kind == ChunkKind.TOOL_RESULT]
    assert len(tool_rows) == 1
    payload = json.loads(tool_rows[0].payload["content"])
    assert payload == 42
