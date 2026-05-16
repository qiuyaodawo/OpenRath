"""Integration tests for the :data:`ChunkAppendHook` produced by :func:`persist_chunks`."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from rath.backend import get
from rath.flow.agent_param import AgentParam
from rath.llm import (
    Provider,
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFunctionTool,
)
from rath.session import Session
from rath.session.loop import run_session_loop, sink_chunk_print
from rath.session.persistence import (
    close_session_writers,
    compose_hooks,
    list_persisted_sessions,
    load_session,
    persist_chunks,
)


class _Script:
    """A ScriptedSessionLoopExecutor-equivalent that returns canned completions."""

    def __init__(self, *responses: RathLLMChatResponse) -> None:
        self._queue: list[RathLLMChatResponse] = list(responses)

    def complete(self, req: object) -> RathLLMChatResponse:
        del req
        return self._queue.pop(0)

    def dispatch_tool(
        self, session: object, tool: object, arguments: object
    ) -> object:
        del session, tool, arguments
        return {"ok": True}

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        return ()


def _simple_response(text: str) -> RathLLMChatResponse:
    return RathLLMChatResponse(
        id="resp",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason="stop",
                message=RathLLMAssistantMessage(role="assistant", content=text),
            ),
        ),
        created=0,
        model="test-model",
    )


def test_persist_chunks_writes_full_transcript(
    _isolate_openrath_home: Path,
) -> None:
    """End-to-end: scripted loop + persist hook → load_session round-trips."""
    backend = get("local")
    agent = AgentParam(
        Session.from_agent_prompt("be brief"), Provider(model="x")
    )
    hook = persist_chunks(sandbox_handle_id="sb-test")
    with backend.open() as sb:
        user = Session.from_user_message("hello").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=_Script(_simple_response("hi there")),
            chunk_print=hook,
        )
    close_session_writers(hook)

    loaded = load_session(out.id)
    assert loaded.closed is True
    # The user row plus the assistant reply are both persisted.
    kinds = [row.kind.value for row in loaded.chunk_table.rows]
    assert kinds == ["user", "assistant"]
    assert loaded.chunk_table.rows[1].payload["content"] == "hi there"
    assert loaded.header.sandbox_handle_id == "sb-test"
    # list_persisted_sessions sees it.
    metas = list_persisted_sessions()
    assert any(m.id == out.id for m in metas)


def test_compose_hooks_invokes_all_in_order(
    _isolate_openrath_home: Path,
) -> None:
    """Each composed hook sees exactly the same (row, index) sequence, in order."""
    seen_a: list[int] = []
    seen_b: list[int] = []
    order: list[str] = []

    def hook_a(row: object, index: int, session: object) -> None:
        del row, session
        seen_a.append(index)
        order.append("a")

    def hook_b(row: object, index: int, session: object) -> None:
        del row, session
        seen_b.append(index)
        order.append("b")

    composed = compose_hooks(hook_a, hook_b)
    backend = get("local")
    agent = AgentParam(
        Session.from_agent_prompt("be brief"), Provider(model="x")
    )
    with backend.open() as sb:
        user = Session.from_user_message("hi").with_sandbox(sb)
        run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=_Script(_simple_response("ok")),
            chunk_print=composed,
        )
    # Both hooks fire on the same indices and in lockstep ("a" always
    # immediately followed by "b" because compose_hooks invokes them in
    # order for each chunk).
    assert seen_a == seen_b
    assert len(seen_a) >= 1
    assert order == ["a", "b"] * len(seen_a)


def test_compose_with_sink_print_writes_disk_and_screen(
    _isolate_openrath_home: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    backend = get("local")
    agent = AgentParam(
        Session.from_agent_prompt("be brief"), Provider(model="x")
    )
    composed = compose_hooks(persist_chunks(), sink_chunk_print())
    with backend.open() as sb:
        user = Session.from_user_message("hi").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=_Script(_simple_response("ok")),
            chunk_print=composed,
        )
    close_session_writers(composed)
    # Persisted to disk — includes the user row even though the loop only
    # fires hooks for newly-appended rows (the persist hook catches up the
    # seed rows on its first call).
    loaded = load_session(out.id)
    kinds = [r.kind.value for r in loaded.chunk_table.rows]
    assert kinds == ["user", "assistant"]
    assert any(r.payload.get("content") == "ok" for r in loaded.chunk_table.rows)
    # Printed to stdout: the loop only notifies its chunk_print for newly
    # appended rows (assistant + tool_result), so the seeded user row is
    # NOT echoed via sink_chunk_print. The assistant turn is.
    out_text = capsys.readouterr().out
    assert "assistant" in out_text
    assert "'ok'" in out_text


def test_close_without_persist_chunks_is_noop(_isolate_openrath_home: Path) -> None:
    def plain_hook(row: object, index: int, session: object) -> None:
        del row, index, session

    assert close_session_writers(plain_hook) == ()


@pytest.fixture
def _persist_hook() -> Iterator[object]:
    yield persist_chunks()


def test_writer_survives_multiple_chunks_via_loop(
    _isolate_openrath_home: Path, _persist_hook: object
) -> None:
    backend = get("local")
    agent = AgentParam(
        Session.from_agent_prompt("respond twice"), Provider(model="x")
    )
    with backend.open() as sb:
        user = Session.from_user_message("hi").with_sandbox(sb)
        out = run_session_loop(
            user,
            agent.agent_session,
            agent_provider=agent.provider,
            executor=_Script(_simple_response("first turn")),
            chunk_print=_persist_hook,
        )
    close_session_writers(_persist_hook)
    loaded = load_session(out.id)
    # user + assistant ⇒ 2 rows.
    assert len(loaded.chunk_table.rows) == 2
