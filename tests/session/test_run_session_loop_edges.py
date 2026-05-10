"""Error paths and iteration caps in ``run_session_loop`` (scripted LLM)."""

from __future__ import annotations

import json
import sys

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
def _clear_registry() -> None:
    yield
    session_registry().set_active(None)


def _write_tool_response(tcid: str = "w") -> RathLLMChatResponse:
    body = {"path": "_edge_touch.txt", "content": "e"}
    return RathLLMChatResponse(
        id="edge-loop",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="tool_calls",
                message=RathLLMAssistantMessage(
                    tool_calls=(
                        RathLLMToolCallPart(
                            id=tcid,
                            type="function",
                            function=RathLLMToolCallFunction(
                                name="write_workspace_file",
                                arguments=json.dumps(body),
                                arguments_parsed=body,
                                arguments_parse_error=False,
                            ),
                        ),
                    ),
                ),
            ),
        ),
        created=0,
        model="script",
    )


def _shell_echo_cmd(marker: str) -> str:
    if sys.platform == "win32":
        return f"cmd /c echo {marker}"
    return f"echo {marker}"


def test_missing_user_sandbox_raises() -> None:
    executor = ScriptedSessionLoopExecutor([])
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    user = Session.from_user_message("no sandbox attached")
    with pytest.raises(RuntimeError, match="no sandbox to take"):
        run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )


def test_tool_arguments_parse_error_surfaces_in_tool_chunk() -> None:
    part = RathLLMToolCallPart(
        id="bad",
        type="function",
        function=RathLLMToolCallFunction(
            name="run_shell_command",
            arguments="{",
            arguments_parsed=None,
            arguments_parse_error=True,
        ),
    )
    resp = RathLLMChatResponse(
        id="badargs",
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
    stop = RathLLMChatResponse(
        id="stop",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="done"),
            ),
        ),
        created=2,
        model="script",
    )
    executor = ScriptedSessionLoopExecutor([resp, stop])

    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("s"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("x").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    tool_rows = [r for r in out.chunk_table.rows if r.kind == ChunkKind.TOOL_RESULT]
    assert len(tool_rows) >= 1
    payload = json.loads(tool_rows[0].payload["content"])
    assert payload.get("ok") is False
    assert payload.get("error_kind") == "invalid_tool_arguments"


def test_unknown_tool_name_surfaces_in_tool_chunk() -> None:
    part = RathLLMToolCallPart(
        id="u",
        type="function",
        function=RathLLMToolCallFunction(
            name="totally_unknown_tool_xx",
            arguments="{}",
            arguments_parsed={},
            arguments_parse_error=False,
        ),
    )
    resp = RathLLMChatResponse(
        id="unk",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="tool_calls",
                message=RathLLMAssistantMessage(tool_calls=(part,)),
            ),
        ),
        created=2,
        model="script",
    )
    stop = RathLLMChatResponse(
        id="stop2",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="done"),
            ),
        ),
        created=3,
        model="script",
    )
    executor = ScriptedSessionLoopExecutor([resp, stop])
    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("s"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("x").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    tool_rows = [r for r in out.chunk_table.rows if r.kind == ChunkKind.TOOL_RESULT]
    assert len(tool_rows) >= 1
    payload = json.loads(tool_rows[0].payload["content"])
    assert payload.get("ok") is False
    assert payload.get("error_kind") == "tool_resolve_failed"


def test_max_tool_rounds_caps_iterations_without_final_stop() -> None:
    scripted = [_write_tool_response(f"w{i}") for i in range(20)]
    executor = ScriptedSessionLoopExecutor(scripted)

    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("cap"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("loop").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
            max_tool_rounds=3,
        )

    tool_results = sum(
        1 for r in out.chunk_table.rows if r.kind == ChunkKind.TOOL_RESULT
    )
    assert tool_results == 3


def test_shell_command_puts_stdout_json_in_tool_chunk() -> None:
    marker = "RATH_SHELL_LINE_442"
    body = {"cmd": _shell_echo_cmd(marker)}
    part = RathLLMToolCallPart(
        id="sh",
        type="function",
        function=RathLLMToolCallFunction(
            name="run_shell_command",
            arguments=json.dumps(body),
            arguments_parsed=body,
            arguments_parse_error=False,
        ),
    )
    first = RathLLMChatResponse(
        id="s1",
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
        id="s2",
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
    agent = AgentParam(Session.from_agent_prompt("sh"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("run echo").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    blob = "".join(
        r.payload["content"]
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.TOOL_RESULT
    )
    assert marker in blob
    seen_cmd_json = False
    for r in out.chunk_table.rows:
        if r.kind != ChunkKind.TOOL_RESULT:
            continue
        data = json.loads(r.payload["content"])
        if "stdout" not in data:
            continue
        assert marker in data["stdout"]
        assert data.get("exit_code") == 0
        seen_cmd_json = True
        break
    assert seen_cmd_json


class _ExplodingExecutor(ScriptedSessionLoopExecutor):
    """Fails tool dispatch to exercise loop scheme A wrapping."""

    def dispatch_tool(self, session, call):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated dispatch failure")


def test_dispatch_exception_surfaces_in_tool_chunk() -> None:
    body = {"cmd": "echo x"}
    part = RathLLMToolCallPart(
        id="ex",
        type="function",
        function=RathLLMToolCallFunction(
            name="run_shell_command",
            arguments=json.dumps(body),
            arguments_parsed=body,
            arguments_parse_error=False,
        ),
    )
    first = RathLLMChatResponse(
        id="e1",
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
        id="e2",
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
    executor = _ExplodingExecutor([first, second])
    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("ex"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("x").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    tool_rows = [r for r in out.chunk_table.rows if r.kind == ChunkKind.TOOL_RESULT]
    assert len(tool_rows) == 1
    payload = json.loads(tool_rows[0].payload["content"])
    assert payload.get("ok") is False
    assert payload.get("error_kind") == "tool_execution_exception"
    assert "RuntimeError" in payload.get("message", "")
