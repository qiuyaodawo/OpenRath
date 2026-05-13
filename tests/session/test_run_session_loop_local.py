"""``run_session_loop`` with :class:`~rath.backend.local.LocalBackend` and scripted completions."""

from __future__ import annotations

import json

import pytest

from rath.backend import get
from rath.flow.agent_param import AgentParam, Provider
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
    agent = AgentParam(
        Session.from_agent_prompt("You are a scripted test assistant."),
        Provider(),
    )

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.from_user_message("Say something short.").with_sandbox(sandbox)
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


def test_run_session_loop_chunk_print_hook_called() -> None:
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
    agent = AgentParam(
        Session.from_agent_prompt("You are a scripted test assistant."),
        Provider(),
    )
    seen: list[tuple[int, str]] = []

    def _record(row: object, index: int, sess: Session) -> None:
        del sess
        from rath.session.chunk import ChunkRow

        assert isinstance(row, ChunkRow)
        seen.append((index, row.kind.value))

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.from_user_message("Say something short.").with_sandbox(sandbox)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
            chunk_print=_record,
        )

    assert seen == [(1, "assistant")]
    assert out.chunk_table.rows[-1].kind == ChunkKind.ASSISTANT


def test_run_session_compress_chunk_print_hook_called() -> None:
    from rath.session import run_session_compress

    scripted = RathLLMChatResponse(
        id="c1",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="compressed narrative"),
            ),
        ),
        created=9,
        model="scripted",
    )
    executor = ScriptedSessionLoopExecutor([scripted])
    agent_sess = Session.from_agent_prompt("You compress transcripts.")

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.from_user_message("Original long user text.").with_sandbox(
            sandbox
        )
        marks: list[tuple[int, str]] = []

        def _hook(row: object, index: int, session: Session) -> None:
            del session
            from rath.session.chunk import ChunkRow

            assert isinstance(row, ChunkRow)
            marks.append((index, row.kind.value))

        out = run_session_compress(
            user,
            agent_sess,
            agent_provider=Provider(api_key="k", model="scripted"),
            executor=executor,
            register_sessions=False,
            chunk_print=_hook,
        )

    assert marks == [(0, "user")]
    assert "compressed narrative" in out.chunk_table.rows[0].payload.get(
        "content", ""
    )


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
    agent = AgentParam(
        Session.from_agent_prompt("Scripted tool harness."),
        Provider(),
    )

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.from_user_message("Write the marker file.").with_sandbox(sandbox)
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
