"""Async session loop: alternate LLM completions with sandbox tool execution."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from rath.backend import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileWriteResult,
    ToolResult,
)
from rath.flow.tool import (
    FlowToolCall,
    ToolTable,
    global_tool_table,
    register_builtin_session_tools,
)
from rath.llm import (
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFunctionTool,
    RathLLMMessage,
)
from rath.session.chunk import (
    ChunkTable,
    assistant_turn_chunk,
    chunk_table_to_messages,
    tool_feedback_chunk,
)
from rath.session.graph import SessionLineage
from rath.session.manager import session_registry
from rath.session.session import Session


@runtime_checkable
class SessionLoopExecutor(Protocol):
    """Runs LLM completions and dispatches sandbox tools for :func:`run_session_loop`."""

    async def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run one chat completion."""

    async def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        """Execute ``call`` on the session sandbox."""

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        """Function tool definitions for OpenAI-style ``tools`` in requests."""


def _chat_request_from_loop(
    messages: tuple[RathLLMMessage, ...],
    tools: tuple[RathLLMFunctionTool, ...] | None,
    prefs: AgentLLMProvider,
    *,
    default_tool_choice: Any,
) -> RathLLMChatRequest:
    """Fold :class:`~rath.flow.agent.AgentLLMProvider` into a concrete request."""

    return RathLLMChatRequest(
        messages=messages,
        tools=tools,
        tool_choice=prefs.tool_choice
        if prefs.tool_choice is not None
        else default_tool_choice,
        parallel_tool_calls=prefs.parallel_tool_calls,
        model=prefs.model,
        temperature=prefs.temperature,
        top_p=prefs.top_p,
        max_completion_tokens=prefs.max_completion_tokens,
        max_tokens=prefs.max_tokens,
        stop=prefs.stop,
        n=prefs.n,
        seed=prefs.seed,
        frequency_penalty=prefs.frequency_penalty,
        presence_penalty=prefs.presence_penalty,
        response_format=prefs.response_format,
        logit_bias=prefs.logit_bias,
        logprobs=prefs.logprobs,
        top_logprobs=prefs.top_logprobs,
        reasoning_effort=prefs.reasoning_effort,
        verbosity=prefs.verbosity,
        metadata=prefs.metadata,
        user=prefs.user,
        store=prefs.store,
        service_tier=prefs.service_tier,
        extra_create_args=prefs.extra_create_args,
    )


def _summarize_tool_result(_call: FlowToolCall, raw: ToolResult | bool) -> str:
    """JSON text for the next ``role=tool`` message."""

    if isinstance(raw, bool):
        return json.dumps({"ok": raw})
    if isinstance(raw, CommandResult):
        return json.dumps(
            {
                "exit_code": raw.exit_code,
                "stdout": raw.stdout.decode("utf-8", errors="replace"),
                "stderr": raw.stderr.decode("utf-8", errors="replace"),
                "elapsed_ms": raw.elapsed_ms,
            }
        )
    if isinstance(raw, FileContent):
        data = raw.data
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        text = str(data)
        if len(text) > 12_000:
            text = text[:12_000] + "...(truncated)"
        return json.dumps({"data": text})
    if isinstance(raw, FileEntries):
        payload = [
            {"name": e.name, "path": e.path, "is_dir": e.is_dir}
            for e in raw.entries[:500]
        ]
        return json.dumps({"entries": payload})
    if isinstance(raw, FileWriteResult):
        return json.dumps({"bytes_written": raw.bytes_written})
    if isinstance(raw, CodeResult):
        stdout = raw.stdout.decode("utf-8", errors="replace")
        stderr = raw.stderr.decode("utf-8", errors="replace")
        return json.dumps(
            {
                "text": raw.text,
                "stdout": stdout,
                "stderr": stderr,
                "error": raw.error,
            }
        )
    return json.dumps({"type": type(raw).__name__, "note": "unserialised result"})


async def run_session_loop(
    user_session: Session,
    agent: Agent,
    *,
    executor: SessionLoopExecutor,
    tool_table: ToolTable | None = None,
    max_tool_rounds: int = 16,
) -> Session:
    """Run one multi-turn assistant pass with optional tool rounds.

    Rebinds the sandbox from ``user_session`` onto the returned :class:`~rath.session.Session`.
    Sampling options come from ``agent.provider``; model access remains on ``executor``.
    """

    table = tool_table or global_tool_table()
    register_builtin_session_tools(table)

    system_session = agent.agent_session
    prefs = agent.provider

    rows_list: list = list(user_session.chunk_table.rows)
    sb = user_session.take_sandbox()
    out = Session(
        chunk_table=ChunkTable(rows=tuple(rows_list)),
        sandbox=sb,
        lineage=SessionLineage(
            producer_user_session_id=user_session.id,
            producer_system_session_id=system_session.id,
        ),
    )
    reg = session_registry()
    reg.register(user_session)
    reg.register(system_session)
    reg.register(out)
    reg.set_active(out)

    tool_schemas = executor.tool_schemas()
    if not tool_schemas:
        tool_schemas = table.schemas()

    for _ in range(max_tool_rounds):
        head = chunk_table_to_messages(system_session.chunk_table)
        tail = chunk_table_to_messages(ChunkTable(rows=tuple(rows_list)))
        messages = head + tail

        req = _chat_request_from_loop(
            messages,
            tool_schemas,
            prefs,
            default_tool_choice="auto",
        )
        resp = await executor.complete(req)
        choice = resp.primary_choice
        msg = choice.message
        tcalls = msg.tool_calls

        if tcalls:
            rows_list.append(
                assistant_turn_chunk(tool_calls=tcalls, content=msg.content)
            )
            for tc in tcalls:
                parsed = tc.function.arguments_parsed
                if parsed is None or tc.function.arguments_parse_error:
                    raise ValueError(
                        f"tool {tc.function.name!r} returned non-JSON arguments",
                    )
                call = table.build(tc.function.name, parsed)
                raw = await executor.dispatch_tool(out, call)
                body = _summarize_tool_result(call, raw)
                rows_list.append(
                    tool_feedback_chunk(tc.id, tc.function.name, body)
                )
            continue

        rows_list.append(
            assistant_turn_chunk(tool_calls=None, content=msg.content)
        )
        if choice.finish_reason in ("stop", "length", "content_filter"):
            break

    out.chunk_table = ChunkTable(rows=tuple(rows_list))
    reg.set_active(out)
    return out


__all__ = [
    "SessionLoopExecutor",
    "run_session_loop",
]
