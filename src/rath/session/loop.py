"""Tool-aware session loop — async orchestration for chat + sandbox tools.

**Async model:** this module is **async-first**. The sync LLM client runs inside
``anyio.to_thread.run_sync`` via :class:`DefaultSessionLoopProvider`. Do **not**
nest ``anyio.run()`` / ``asyncio.run()`` inside an already running loop.
"""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

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
class SessionLoopProvider(Protocol):
    """Strategy object for LLM + sandbox execution (no Workflow import)."""

    async def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run one chat completion."""

    async def dispatch_tool(
        self,
        session: Session,
        call: FlowToolCall,
    ) -> ToolResult | bool:
        """Execute ``call`` on the session sandbox."""

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        """OpenAI function defs (ToolTable-backed)."""


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
    system_session: Session,
    provider: SessionLoopProvider,
    *,
    tool_table: ToolTable | None = None,
    max_tool_rounds: int = 16,
) -> Session:
    """Run ``system + user`` messages with tool calls; return a new Session.

    The returned session **rebinds** the sandbox taken from ``user_session``.
    After success, ``user_session`` no longer holds that sandbox.
    """

    table = tool_table or global_tool_table()
    register_builtin_session_tools(table)

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

    tool_schemas = provider.tool_schemas()
    if not tool_schemas:
        tool_schemas = table.schemas()

    for _ in range(max_tool_rounds):
        head = chunk_table_to_messages(system_session.chunk_table)
        tail = chunk_table_to_messages(ChunkTable(rows=tuple(rows_list)))
        messages = head + tail

        req = RathLLMChatRequest(
            messages=messages,
            model=None,
            tools=tool_schemas,
            tool_choice="auto",
        )
        resp = await provider.complete(req)
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
                raw = await provider.dispatch_tool(out, call)
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
    "SessionLoopProvider",
    "run_session_loop",
]
