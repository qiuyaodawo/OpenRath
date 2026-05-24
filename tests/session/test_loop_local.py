"""``run_session_loop`` against the local backend with scripted completions.

Consolidated from (every test function name preserved verbatim):
- test_run_session_loop_local.py        (stop + compress + tool write)
- test_run_session_loop_edges.py        (error paths, max_tool_rounds, default executor)
- test_loop_chunk_table_growth.py       (chunk_table identity invariant per turn)
- test_loop_stream.py                   (on_event / StreamingExecutor)
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from typing import Any, Iterator

import pytest

from rath.backend import get
from rath.flow.agent_param import AgentParam, Provider
from rath.flow.tool.base import FlowToolCall
from rath.llm import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMStreamDelta,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.session import (
    Session,
    run_session_loop,
    session_registry,
)
from rath.session.chunk import ChunkKind
from rath.session.loop import StreamingExecutor
from tests.session.scripted_loop_executor import ScriptedSessionLoopExecutor


@pytest.fixture(autouse=True)
def _clear_active_session_registry() -> None:
    yield
    session_registry().set_active(None)


def _shell_echo_cmd(marker: str) -> str:
    if sys.platform == "win32":
        return f"cmd /c echo {marker}"
    return f"echo {marker}"


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


# ---------------------------------------------------------------------------
# happy paths
# ---------------------------------------------------------------------------


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
        user = Session.from_user_message("Say something short.").bind_sandbox(sandbox)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    assert user.sandbox is sandbox
    assert out.sandbox is sandbox
    assert sandbox.refcount == 2
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


def test_run_session_compress_without_sandbox() -> None:
    """compress must accept a user_session that never called .to(...)."""
    from rath.session import run_session_compress

    scripted = RathLLMChatResponse(
        id="c-no-sb",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content="short summary"),
            ),
        ),
        created=10,
        model="scripted",
    )
    executor = ScriptedSessionLoopExecutor([scripted])
    user = Session.from_user_message("Some long transcript.")
    agent_sess = Session.from_agent_prompt("You compress transcripts.")

    out = run_session_compress(
        user,
        agent_sess,
        agent_provider=Provider(api_key="k", model="scripted"),
        executor=executor,
        register_sessions=False,
    )

    assert out.sandbox is None
    assert out.sandbox_backend is None
    assert "short summary" in out.chunk_table.rows[0].payload.get("content", "")


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
        user = Session.from_user_message("Write the marker file.").bind_sandbox(sandbox)
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


# ---------------------------------------------------------------------------
# error paths and iteration caps
# ---------------------------------------------------------------------------


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
        user = Session.from_user_message("x").bind_sandbox(sb)
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
        user = Session.from_user_message("x").bind_sandbox(sb)
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
    assert payload.get("error_kind") == "unknown_tool"


def test_max_tool_rounds_caps_iterations_without_final_stop() -> None:
    scripted = [_write_tool_response(f"w{i}") for i in range(20)]
    executor = ScriptedSessionLoopExecutor(scripted)

    backend = get("local")
    agent = AgentParam(Session.from_agent_prompt("cap"), Provider())
    with backend.open() as sb:
        user = Session.from_user_message("loop").bind_sandbox(sb)
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
        user = Session.from_user_message("run echo").bind_sandbox(sb)
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
    """Fails tool dispatch to exercise loop JSON error wrapping for tool results."""

    def dispatch_tool(self, session, tool, arguments):  # type: ignore[no-untyped-def]
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
        user = Session.from_user_message("x").bind_sandbox(sb)
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


def test_default_executor_requires_api_key_somewhere(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """With no Provider.api_key, no env fallback, and no config file, the
    default executor must raise from the client (not from a redundant
    pre-check in the loop)."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_API_KEY", raising=False)
    # Isolate the config-file tier too — point OPENRATH_HOME at an empty dir.
    monkeypatch.setenv("OPENRATH_HOME", str(tmp_path))
    backend = get("local")
    agent = AgentParam(
        Session.from_agent_prompt("sys"),
        Provider(model="phony-model-id"),
    )
    with backend.open() as sb:
        user = Session.from_user_message("x").bind_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
        )
        with pytest.raises(ValueError, match="No API key found"):
            out.synchronize()


def test_max_tool_rounds_truncation_emits_warning_and_lineage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A loop that keeps requesting tool calls past max_tool_rounds must log a
    warning and stamp ('loop.truncated', True) in lineage_extras, so callers
    can detect the dangling tool_result tail without diffing chunk rows."""
    scripted = [_write_tool_response(f"tc{i}") for i in range(5)]
    executor = ScriptedSessionLoopExecutor(scripted)
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    backend = get("local")

    with backend.open() as sb:
        user = Session.from_user_message("trigger loop budget").bind_sandbox(sb)
        with caplog.at_level(logging.WARNING, logger="rath.session.loop"):
            out = run_session_loop(
                user,
                agent.agent_session,
                agent_provider=agent.provider,
                executor=executor,
                max_tool_rounds=2,
            )
            out.synchronize()

    assert ("loop.truncated", True) in out.lineage_extras
    assert any("max_tool_rounds" in rec.message for rec in caplog.records)
    # Last row should still be a tool_result (the symptom this warning
    # exists to flag).
    assert out.chunk_table.rows[-1].kind == ChunkKind.TOOL_RESULT


# ---------------------------------------------------------------------------
# chunk_table growth invariant
# ---------------------------------------------------------------------------


class _RecordingTool(FlowToolCall):
    """Tool that records ``id(session.chunk_table)`` on every invocation."""

    def __init__(self) -> None:
        self.observed_ids: list[int] = []

    @property
    def name(self) -> str:
        return "record_id"

    @property
    def description(self) -> str | None:
        return "record session.chunk_table identity"

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    def __call__(self, session: Session, arguments: Mapping[str, Any]) -> Any:
        self.observed_ids.append(id(session.chunk_table))
        return "ok"


def _tool_call_response(resp_id: str, call_ids: list[str]) -> RathLLMChatResponse:
    parts = tuple(
        RathLLMToolCallPart(
            id=cid,
            type="function",
            function=RathLLMToolCallFunction(
                name="record_id",
                arguments="{}",
                arguments_parsed={},
                arguments_parse_error=False,
            ),
        )
        for cid in call_ids
    )
    return RathLLMChatResponse(
        id=resp_id,
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="tool_calls",
                message=RathLLMAssistantMessage(content=None, tool_calls=parts),
            ),
        ),
        created=1,
        model="scripted",
    )


def _stop_response(resp_id: str, text: str) -> RathLLMChatResponse:
    return RathLLMChatResponse(
        id=resp_id,
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(content=text),
            ),
        ),
        created=2,
        model="scripted",
    )


def test_chunk_table_identity_is_stable_within_a_turn() -> None:
    """Three tools per turn must observe the same ``chunk_table`` identity."""
    turn1 = _tool_call_response("t1", ["t1-a", "t1-b", "t1-c"])
    turn2 = _tool_call_response("t2", ["t2-a", "t2-b", "t2-c"])
    stop = _stop_response("t3", "done")
    executor = ScriptedSessionLoopExecutor([turn1, turn2, stop])

    tool = _RecordingTool()

    backend = get("local")
    with backend.open() as sandbox:
        user = Session.from_user_message("go").bind_sandbox(sandbox)
        agent = Session.from_agent_prompt("scripted")
        out = run_session_loop(
            user,
            agent,
            agent_provider=Provider(),
            tools=[tool],
            executor=executor,
        )
        # Lazy facade: block on the in-flight materialization before asserting
        # that tools observed a stable ``chunk_table`` identity per turn.
        out.synchronize()

    assert len(tool.observed_ids) == 6, tool.observed_ids
    turn1_ids = set(tool.observed_ids[:3])
    turn2_ids = set(tool.observed_ids[3:])
    # Within a turn: identical chunk_table object reused for every tool call.
    assert len(turn1_ids) == 1, f"per-row rebuild regression in turn 1: {turn1_ids}"
    assert len(turn2_ids) == 1, f"per-row rebuild regression in turn 2: {turn2_ids}"
    # Across turns: a fresh ChunkTable is materialised before the next round.
    assert turn1_ids != turn2_ids


# ---------------------------------------------------------------------------
# streaming via on_event / StreamingExecutor
# ---------------------------------------------------------------------------


class _ScriptedStreamingClient:
    """Streaming-shaped chat client used to script multi-round loops."""

    def __init__(self, scripts: list[list[RathLLMStreamDelta]]) -> None:
        self._scripts = list(scripts)
        self.provider = Provider(model="scripted")

    def complete_stream(self, req: RathLLMChatRequest) -> Iterator[RathLLMStreamDelta]:
        if not self._scripts:
            raise RuntimeError("scripted stream queue empty")
        for d in self._scripts.pop(0):
            yield d

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        raise NotImplementedError("scripted client is stream-only")


def test_on_event_refuses_non_streaming_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """``on_event`` requires the resolved client to implement complete_stream(req)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-no-network")
    monkeypatch.delenv("OPENRATH_HOME", raising=False)
    agent = AgentParam(
        Session.from_agent_prompt("sys"),
        Provider(provider_kind="anthropic", model="claude-opus-4-7"),
    )
    backend = get("local")
    with backend.open() as sb:
        user = Session.from_user_message("hi").bind_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            on_event=lambda _d: None,
        )
        with pytest.raises(TypeError, match="complete_stream|StreamingChatClient"):
            out.synchronize()


def test_on_event_with_custom_executor_raises() -> None:
    backend = get("local")
    with backend.open() as sb:
        user = Session.from_user_message("hi").bind_sandbox(sb)
        agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
        scripted = StreamingExecutor(_ScriptedStreamingClient([]), lambda _d: None)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=scripted,
            on_event=lambda _d: None,
        )
        with pytest.raises(ValueError, match="custom executor"):
            out.synchronize()


def test_streaming_executor_emits_deltas_and_settles_to_chunk() -> None:
    script = [
        [
            RathLLMStreamDelta(content_delta="Hel"),
            RathLLMStreamDelta(content_delta="lo"),
            RathLLMStreamDelta(finish_reason="stop"),
        ]
    ]
    client = _ScriptedStreamingClient(script)
    events: list[RathLLMStreamDelta] = []
    executor = StreamingExecutor(client, events.append)
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    backend = get("local")

    with backend.open() as sb:
        user = Session.from_user_message("hi").bind_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )
        out.synchronize()

    assert len(events) == 3
    assistant_rows = [
        r.payload.get("content")
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.ASSISTANT
    ]
    assert "Hello" in assistant_rows


def test_streaming_tool_call_then_stop() -> None:
    args = json.dumps({"path": "."})
    script = [
        [
            RathLLMStreamDelta(
                tool_call_index=0, tool_call_id="tc1", tool_call_name_delta="echo_tool"
            ),
            RathLLMStreamDelta(tool_call_index=0, tool_call_args_delta=args),
            RathLLMStreamDelta(finish_reason="tool_calls"),
        ],
        [
            RathLLMStreamDelta(content_delta="done"),
            RathLLMStreamDelta(finish_reason="stop"),
        ],
    ]
    client = _ScriptedStreamingClient(script)
    events: list[RathLLMStreamDelta] = []
    executor = StreamingExecutor(client, events.append)
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    backend = get("local")

    with backend.open() as sb:
        user = Session.from_user_message("trigger").bind_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=executor,
        )

    kinds = [r.kind for r in out.chunk_table.rows]
    assert ChunkKind.TOOL_RESULT in kinds
    assert any(
        r.kind == ChunkKind.ASSISTANT and r.payload.get("content") == "done"
        for r in out.chunk_table.rows
    )
