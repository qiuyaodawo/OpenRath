"""``run_session_loop`` with :class:`~rath.backend.local.LocalBackend` and scripted completions."""

from __future__ import annotations

import json

import pytest

from rath.backend import get
from rath.flow.agent import Agent, Provider
from rath.llm import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.session.chunk import ChunkKind
from rath.session import Session, run_session_loop, session_registry
from tests.session.scripted_loop_executor import ScriptedSessionLoopExecutor


@pytest.fixture(autouse=True)
def _clear_active_session_registry() -> None:
    yield
    session_registry().set_active(None)


def test_run_session_loop_stop_without_tools() -> None:
    scripted = RathLLMChatResponse(
        id="s1",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="final answer"),
            ),
        ),
        created=1,
        model="scripted",
    )
    executor = ScriptedSessionLoopExecutor([scripted])
    agent = Agent(
        Session.from_system_prompt("You are a scripted test assistant."),
        Provider(),
    )

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.user_message("Say something short.").with_sandbox(sandbox)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    assert user.sandbox is None
    assert out.sandbox is sandbox
    assert out.lineage is not None
    assert session_registry().get_active_id() == out.id

    kinds = [r.kind for r in out.chunk_table.rows]
    assert ChunkKind.ASSISTANT in kinds
    last_assistant_payloads = [
        r.payload.get("content")
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.ASSISTANT
    ]
    assert "final answer" in last_assistant_payloads


def test_run_session_loop_write_file_via_tool_then_stop() -> None:
    body = {"path": "_rath_loop_probe.txt", "content": "LOCAL_SCRIPTED_MARKER"}
    arg_str = json.dumps(body)
    tool_part = RathLLMToolCallPart(
        id="tc_write",
        type="function",
        function=RathLLMToolCallFunction(
            name="write_workspace_file",
            arguments=arg_str,
            arguments_parsed=body,
            arguments_parse_error=False,
        ),
    )
    first = RathLLMChatResponse(
        id="m1",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="tool_calls",
                message=RathLLMAssistantMessage(
                    tool_calls=(tool_part,),
                ),
            ),
        ),
        created=2,
        model="scripted",
    )
    second = RathLLMChatResponse(
        id="m2",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="done"),
            ),
        ),
        created=3,
        model="scripted",
    )
    executor = ScriptedSessionLoopExecutor([first, second])
    agent = Agent(
        Session.from_system_prompt("Scripted tool harness."),
        Provider(),
    )

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.user_message("Write the marker file.").with_sandbox(sandbox)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    tool_payloads = [
        json.loads(r.payload["content"])
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.TOOL_RESULT
    ]
    assert any(p.get("bytes_written", 0) > 0 for p in tool_payloads), tool_payloads
