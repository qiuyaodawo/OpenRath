"""Session context compression via one-shot LLM call (:func:`run_session_compress`)."""

from __future__ import annotations

from dataclasses import replace

from rath.llm import (
    Provider,
    RathLLMChatResponse,
    RathLLMMessage,
    add_usage,
)
from rath.session.chat_request_build import provider_into_chat_request
from rath.session.chunk import ChunkTable, chunk_table_to_messages, user_text_chunk
from rath.session.graph import LineageKind, LineageRecorder, SessionLineage
from rath.session.loop import ChunkAppendHook, SessionLoopExecutor
from rath.session.manager import session_registry
from rath.session.provider_builtin import DefaultSessionLoopExecutor
from rath.session.session import Session

_DEFAULT_COMPRESS_INSTRUCTION = (
    "The messages above are a conversation transcript (system/agent context followed "
    "by user-visible turns). Compress them into a shorter narrative that preserves "
    "facts, user goals, and open tasks. Output plain text only, suitable as the "
    "sole replacement user-side transcript — no role labels."
)


def run_session_compress(
    user_session: Session,
    agent_session: Session,
    *,
    agent_provider: Provider,
    executor: SessionLoopExecutor | None = None,
    compress_instruction: str | None = None,
    register_sessions: bool = True,
    chunk_print: ChunkAppendHook | None = None,
) -> Session:
    """Summarize transcript via LLM into a new user-only session (no SYSTEM chunks).

    ``agent_session`` and ``user_session`` chunks are folded into the completion
    request only — they are not copied into ``out.chunk_table``. The returned session
    contains **USER** rows built from the model reply.

    Completions use ``tools=None`` and ``tool_choice=none``. If the model returns tool
    calls, raises ``RuntimeError``.

    When ``executor`` is ``None``, a default executor is built from ``agent_provider``;
    it must carry a non-empty ``api_key``.

    Rebases sandbox from ``user_session`` onto the returned session (same as the loop).

    If ``chunk_print`` is set, it is called once as ``hook(row, 0, out)`` for the
    single compressed **user** row after ``out`` is built (sandbox rebound).
    """

    if executor is None:
        from rath.session.loop import _build_default_client

        executor = DefaultSessionLoopExecutor(_build_default_client(agent_provider))

    instruction = (
        compress_instruction.strip()
        if compress_instruction is not None
        else _DEFAULT_COMPRESS_INSTRUCTION
    )

    head = chunk_table_to_messages(agent_session.chunk_table)
    tail = chunk_table_to_messages(user_session.chunk_table)
    messages: tuple[RathLLMMessage, ...] = (
        head + tail + (RathLLMMessage(role="user", content=instruction),)
    )

    prefs = replace(agent_provider, tool_choice=None)
    req = provider_into_chat_request(
        messages,
        None,
        prefs,
        default_tool_choice="none",
    )

    # Compress is a pure-LLM operation (tool_choice is forced to "none"); a
    # sandbox is only useful for rebinding to the output session. Skip
    # take_sandbox() entirely when the caller has not attached one, so
    # Session.from_user_message("...") works without a prior .to("local").
    sb = None
    if user_session.sandbox is not None or user_session.sandbox_backend is not None:
        sb = user_session.take_sandbox()
    resp = executor.complete(req)
    body = _completion_body(resp)
    if body is None or not str(body).strip():
        raise RuntimeError("run_session_compress: empty model content")

    rows = (user_text_chunk(str(body).strip()),)
    out = Session(
        chunk_table=ChunkTable(rows=rows),
        sandbox_backend=user_session.sandbox_backend,
        _sandbox_open_spec=user_session._sandbox_open_spec,
        lineage=SessionLineage(
            producer_user_session_id=user_session.id,
            producer_system_session_id=agent_session.id,
            operator="run_session_compress",
        ),
        cumulative_usage=add_usage(None, resp.usage),
    )
    if sb is not None:
        out.bind_sandbox(sb)

    LineageRecorder.stamp_new_session(
        out,
        parent_session_ids=(user_session.id, agent_session.id),
        lineage_operator="run_session_compress",
        lineage_kind=LineageKind.OP_SESSION_COMPRESS,
        lineage_extras=(
            ("compression.lossy", True),
            ("compression.rows_out", len(rows)),
        ),
    )

    if register_sessions:
        reg = session_registry()
        reg.register(user_session)
        reg.register(agent_session)
        reg.register(out)
        reg.set_active(out)

    if chunk_print is not None:
        chunk_print(rows[0], 0, out)

    return out


def _completion_body(resp: RathLLMChatResponse) -> str | None:
    choice = resp.primary_choice
    msg = choice.message
    tcalls = msg.tool_calls
    if tcalls:
        raise RuntimeError(
            "run_session_compress: model returned tool calls but tools are disabled"
        )
    fr = choice.finish_reason
    if fr not in ("stop", "length", "content_filter"):
        raise RuntimeError(f"run_session_compress: unexpected finish_reason={fr!r}")
    content = msg.content
    return None if content is None else str(content)


__all__ = ["run_session_compress"]
