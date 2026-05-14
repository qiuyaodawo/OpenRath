"""Streaming session loop (:func:`run_session_loop_stream`)."""

from __future__ import annotations

import json
from typing import Iterator

import pytest

from rath.backend import get
from rath.flow.agent_param import AgentParam, Provider
from rath.llm import (
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMStreamDelta,
    RathLLMTokenUsage,
)
from rath.session import Session, session_registry
from rath.session.chunk import ChunkKind
from rath.session.loop_stream import (
    accumulate_stream_to_response,
    run_session_loop_stream,
)


@pytest.fixture(autouse=True)
def _clear_active() -> None:
    yield
    session_registry().set_active(None)


def test_accumulate_text_stream() -> None:
    deltas = iter(
        [
            RathLLMStreamDelta(content_delta="Hel"),
            RathLLMStreamDelta(content_delta="lo, "),
            RathLLMStreamDelta(content_delta="world!"),
            RathLLMStreamDelta(finish_reason="stop"),
            RathLLMStreamDelta(
                usage=RathLLMTokenUsage(
                    prompt_tokens=5, completion_tokens=3, total_tokens=8
                )
            ),
        ]
    )
    seen: list[RathLLMStreamDelta] = []
    resp = accumulate_stream_to_response(deltas, on_event=seen.append)
    assert resp.primary_choice.message.content == "Hello, world!"
    assert resp.primary_choice.finish_reason == "stop"
    assert resp.usage is not None
    assert resp.usage.total_tokens == 8
    # Every delta was forwarded.
    assert len(seen) == 5


def test_accumulate_tool_call_stream() -> None:
    args_chunks = [json.dumps({"path": "/etc"})[i : i + 4] for i in range(0, 14, 4)]
    deltas: list[RathLLMStreamDelta] = [
        RathLLMStreamDelta(
            tool_call_index=0,
            tool_call_id="tc1",
            tool_call_name_delta="list_files",
        ),
    ]
    for chunk in args_chunks:
        deltas.append(
            RathLLMStreamDelta(
                tool_call_index=0,
                tool_call_args_delta=chunk,
            )
        )
    deltas.append(RathLLMStreamDelta(finish_reason="tool_calls"))
    resp = accumulate_stream_to_response(iter(deltas))
    tc = resp.primary_choice.message.tool_calls
    assert tc is not None and len(tc) == 1
    assert tc[0].id == "tc1"
    assert tc[0].function.name == "list_files"
    assert tc[0].function.arguments_parsed == {"path": "/etc"}
    assert resp.primary_choice.finish_reason == "tool_calls"


class _ScriptedStreamingClient:
    """Fake :class:`~rath.llm.RathOpenAIChatClient`-shape with complete_stream."""

    def __init__(self, scripts: list[list[RathLLMStreamDelta]]) -> None:
        self._scripts = list(scripts)
        # Provider attribute so DefaultSessionLoopExecutor wrapping works.
        self.provider = Provider(model="scripted")

    def complete_stream(self, req: RathLLMChatRequest) -> Iterator[RathLLMStreamDelta]:
        if not self._scripts:
            raise RuntimeError("scripted stream queue empty")
        for d in self._scripts.pop(0):
            yield d

    # complete() so DefaultSessionLoopExecutor's non-streaming path still works
    # if the loop ever calls it (it won't, but the adapter delegates dispatch
    # via DefaultSessionLoopExecutor which only needs complete on its inner).
    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        raise NotImplementedError("scripted client is stream-only")


def test_run_session_loop_stream_refuses_anthropic_provider_kind() -> None:
    """Streaming + Anthropic must fail upfront, not after sessions are stamped."""
    agent = AgentParam(
        Session.from_agent_prompt("sys"),
        Provider(provider_kind="anthropic", model="claude-opus-4-7"),
    )
    backend = get("local")
    with backend.open() as sb:
        user = Session.from_user_message("hi").with_sandbox(sb)
        with pytest.raises(NotImplementedError, match="streaming.*anthropic"):
            run_session_loop_stream(
                user,
                agent.agent_session,
                agent_provider=agent.provider,
            )


def test_run_session_loop_stream_emits_per_delta_and_settles_to_chunk() -> None:
    script = [
        [
            RathLLMStreamDelta(content_delta="Hel"),
            RathLLMStreamDelta(content_delta="lo"),
            RathLLMStreamDelta(finish_reason="stop"),
        ]
    ]
    client = _ScriptedStreamingClient(script)
    agent = AgentParam(Session.from_agent_prompt("sys"), Provider())
    backend = get("local")
    events: list[RathLLMStreamDelta] = []

    with backend.open() as sb:
        user = Session.from_user_message("hi").with_sandbox(sb)
        out = run_session_loop_stream(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            client=client,
            on_event=events.append,
        )

    # All 3 deltas should have been forwarded.
    assert len(events) == 3
    # Final chunk_table holds the assembled assistant message.
    assistant_rows = [
        r.payload.get("content")
        for r in out.chunk_table.rows
        if r.kind == ChunkKind.ASSISTANT
    ]
    assert "Hello" in assistant_rows
