"""Session loop: alternate LLM completions with sandbox tool execution (blocking)."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from typing import Any, Mapping, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel

from rath.backend import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileWriteResult,
    ToolExecutionFailure,
    ToolResult,
)
from rath.flow.tool import (
    FlowToolCall,
    merge_tools_for_loop,
    tools_dict_to_schemas,
)
from rath.llm import (
    Provider,
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFunctionTool,
    add_usage,
    chat_client_for,
)
from rath.session.chat_request_build import provider_into_chat_request
from rath.session.chunk import (
    ChunkRow,
    ChunkTable,
    assistant_turn_chunk,
    chunk_table_to_messages,
    format_chunk_row_brief,
    tool_feedback_chunk,
)
from rath.session.graph import LineageKind, LineageRecorder, SessionLineage
from rath.session.manager import session_registry
from rath.session.provider_builtin import DefaultSessionLoopExecutor
from rath.session.session import Session
from rath.utils.decoding import decode_subprocess_output

logger = logging.getLogger(__name__)

ChunkAppendHook: TypeAlias = Callable[[ChunkRow, int, Session], object]
"""Called after each **new** assistant or tool-result row is appended to the loop session."""

# Legacy alias; prefer :class:`ChunkAppendHook`.
ChunkPrintFn = ChunkAppendHook


def ensure_stdio_utf8() -> None:
    """Best-effort UTF-8 on ``stdout`` / ``stderr`` (e.g. Windows console)."""

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError, TypeError, IsADirectoryError):
            continue


def sink_chunk_print(
    write: Callable[[object], object] | None = None,
) -> ChunkAppendHook:
    """Build a hook that prints one line per appended row via ``write`` (default: :func:`print`).

    On first use, calls :func:`ensure_stdio_utf8` so Unicode (CJK, box-drawing, emoji)
    is not replaced or mangled when the process default encoding is legacy (cp1252, etc.).
    """

    sink = print if write is None else write
    configured = False

    def _hook(row: ChunkRow, index: int, session: Session) -> object:
        nonlocal configured
        if not configured:
            ensure_stdio_utf8()
            configured = True
        del session
        return sink(format_chunk_row_brief(index, row))

    return _hook


def _notify_chunk_append(
    hook: ChunkAppendHook | None,
    rows_list: list[Any],
    out: Session,
) -> None:
    if hook is None:
        return
    idx = len(rows_list) - 1
    hook(rows_list[idx], idx, out)


def _sync_loop_out_rows(out: Session, rows_list: list[Any]) -> None:
    out.chunk_table = ChunkTable(rows=tuple(rows_list))


def _accumulate_usage_and_check_budget(
    out: Session,
    resp: RathLLMChatResponse,
    provider: Provider,
) -> None:
    """Fold ``resp.usage`` into ``out.cumulative_usage`` and trip the budget guard.

    The guard fires **only on the completion that first pushes the running
    total past ``provider.budget_total_tokens``**, never again for the same
    ``out`` session. That keeps a multi-round tool-calling loop from
    re-invoking the callback (or re-logging the warning) every round once the
    cap has already been crossed; callers that want to abort the loop are
    expected to raise :class:`~rath.llm.BudgetExceededError` from the
    callback on that first call.

    The latch is implicit in the prev/new transition (``prev <= cap`` and
    ``new > cap``); no new session state is introduced.
    """
    if resp.usage is None:
        return
    prev_total = (
        out.cumulative_usage.total_tokens if out.cumulative_usage is not None else 0
    )
    out.cumulative_usage = add_usage(out.cumulative_usage, resp.usage)
    cap = provider.budget_total_tokens
    if cap is None or out.cumulative_usage is None:
        return
    new_total = out.cumulative_usage.total_tokens
    if new_total <= cap or prev_total > cap:
        return
    callback = provider.on_budget_exceeded
    if callback is None:
        logger.warning(
            "session %s exceeded budget_total_tokens=%d "
            "(cumulative=%d); no callback configured",
            out.id,
            cap,
            new_total,
        )
        return
    callback(out, out.cumulative_usage)


@runtime_checkable
class SessionLoopExecutor(Protocol):
    """Runs completions and tool dispatch used by ``run_session_loop``."""

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run one chat completion."""

    def dispatch_tool(
        self,
        session: Session,
        tool: FlowToolCall,
        arguments: Mapping[str, Any],
    ) -> Any:
        """Run ``tool`` with JSON ``arguments`` (typically ``tool(session, arguments)``)."""

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        """Tool specs for OpenAI-style ``tools``. Empty tuple defers to the loop-local merged registry."""


def _loop_tool_error_payload(
    kind: str, message: str, *, detail: str | None = None
) -> str:
    """JSON string for a tool failure returned as the next ``role=tool`` body."""

    payload: dict[str, Any] = {
        "ok": False,
        "error_kind": kind,
        "message": message,
    }
    if detail:
        payload["detail"] = detail[:4000]
    return json.dumps(payload)


def _summarize_inline_result(obj: Any) -> str:
    """JSON text for arbitrary tool return values."""

    try:
        if isinstance(obj, BaseModel):
            payload: Any = obj.model_dump(mode="json")
        else:
            payload = obj
        text = json.dumps(payload, ensure_ascii=False, default=str)
        if len(text) > 48_000:
            text = text[:48_000] + "...(truncated)"
        return text
    except TypeError:
        return json.dumps({"repr": repr(obj), "type": type(obj).__name__})


def _summarize_tool_result(_call: FlowToolCall, raw: ToolResult | bool) -> str:
    """JSON text for the next ``role=tool`` message."""

    if isinstance(raw, ToolExecutionFailure):
        return json.dumps(
            {
                "ok": False,
                "error_kind": raw.kind,
                "message": raw.message,
                **({"detail": raw.detail} if raw.detail else {}),
            }
        )
    if isinstance(raw, bool):
        return json.dumps({"ok": raw})
    if isinstance(raw, CommandResult):
        return json.dumps(
            {
                "exit_code": raw.exit_code,
                "stdout": decode_subprocess_output(raw.stdout),
                "stderr": decode_subprocess_output(raw.stderr),
                "elapsed_ms": raw.elapsed_ms,
            }
        )
    if isinstance(raw, FileContent):
        data = raw.data
        if isinstance(data, bytes):
            data = decode_subprocess_output(data)
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
        stdout = decode_subprocess_output(raw.stdout)
        stderr = decode_subprocess_output(raw.stderr)
        return json.dumps(
            {
                "text": raw.text,
                "stdout": stdout,
                "stderr": stderr,
                "error": raw.error,
            }
        )
    return json.dumps({"type": type(raw).__name__, "note": "unserialised result"})


def _summarize_dispatch_result(tool: FlowToolCall, raw: Any) -> str:
    if isinstance(raw, ToolResult) or isinstance(raw, bool):
        return _summarize_tool_result(tool, raw)
    return _summarize_inline_result(raw)


def run_session_loop(
    user_session: Session,
    agent_session: Session,
    *,
    agent_provider: Provider,
    tools: list[FlowToolCall] | None = None,
    executor: SessionLoopExecutor | None = None,
    max_tool_rounds: int = 16,
    chunk_print: ChunkAppendHook | None = None,
) -> Session:
    """Run one multi-turn assistant pass with optional tool rounds.

    Built-in tools come from :func:`~rath.flow.tool.global_system_tools`; pass
    instantiated :class:`~rath.flow.tool.FlowToolCall` objects in ``tools`` to add
    or shadow is disallowed — user names must not collide with built-ins.

    Rebases ``BackendSandbox`` from ``user_session`` onto the returned session.
    LLM routing/sampling kwargs come from ``agent_provider``
    (:class:`~rath.llm.Provider`); completions and tool dispatch go through
    ``executor``.     When ``executor`` is omitted, builds a fresh
    :class:`~rath.session.provider_builtin.DefaultSessionLoopExecutor`
    wrapping :class:`~rath.llm.client.RathOpenAIChatClient` built from
    ``agent_provider`` (which must include a non-empty ``api_key``).

    Message assembly concatenates ``agent_session.chunk_table`` ahead of user rows for
    the LLM; head rows stay out of ``out.chunk_table`` (assistant + tool-result only).

    When ``session_graph_mode()`` is true, stamps flat lineage on ``out`` and attaches
    legacy :class:`~rath.session.graph.SessionLineage`.

    If ``chunk_print`` is set, it is invoked as ``hook(row, index, out)`` after **each**
    new assistant or tool-result row is appended (indices follow ``out.chunk_table.rows``).
    Use :func:`sink_chunk_print` to print a one-line summary per row; bare :func:`print`
    is not suitable (wrong arity).
    """

    table = merge_tools_for_loop(tools)

    if executor is None:
        executor = DefaultSessionLoopExecutor(chat_client_for(agent_provider))

    prefs = agent_provider

    rows_list: list[Any] = list(user_session.chunk_table.rows)
    sb = user_session.take_sandbox()
    out = Session(
        chunk_table=ChunkTable(rows=tuple(rows_list)),
        sandbox=sb,
        sandbox_backend=user_session.sandbox_backend,
        _sandbox_open_spec=user_session._sandbox_open_spec,
        lineage=SessionLineage(
            producer_user_session_id=user_session.id,
            producer_system_session_id=agent_session.id,
        ),
    )
    LineageRecorder.stamp_new_session(
        out,
        parent_session_ids=(user_session.id, agent_session.id),
        lineage_operator="run_session_loop",
        lineage_kind=LineageKind.OP_SESSION_LOOP,
    )
    reg = session_registry()
    reg.register(user_session)
    reg.register(agent_session)
    reg.register(out)
    reg.set_active(out)

    tool_schemas = executor.tool_schemas()
    if not tool_schemas:
        tool_schemas = tools_dict_to_schemas(table)

    for _ in range(max_tool_rounds):
        head = chunk_table_to_messages(agent_session.chunk_table)
        tail = chunk_table_to_messages(ChunkTable(rows=tuple(rows_list)))
        messages = head + tail

        req = provider_into_chat_request(
            messages,
            tool_schemas,
            prefs,
            default_tool_choice="auto",
        )
        resp = executor.complete(req)
        _accumulate_usage_and_check_budget(out, resp, prefs)
        choice = resp.primary_choice
        msg = choice.message
        tcalls = msg.tool_calls

        if tcalls:
            rows_list.append(
                assistant_turn_chunk(tool_calls=tcalls, content=msg.content)
            )
            _sync_loop_out_rows(out, rows_list)
            _notify_chunk_append(chunk_print, rows_list, out)
            for tc in tcalls:
                tool_name = tc.function.name
                if (
                    tc.function.arguments_parsed is None
                    or tc.function.arguments_parse_error
                ):
                    raw_dump = tc.function.arguments or ""
                    if len(raw_dump) > 2000:
                        raw_dump = raw_dump[:2000] + "...(truncated)"
                    body = _loop_tool_error_payload(
                        "invalid_tool_arguments",
                        (
                            f"tool {tool_name!r} returned non-JSON "
                            f"or unparseable arguments"
                        ),
                        detail=raw_dump,
                    )
                else:
                    flow_tool = table.get(tool_name)
                    if flow_tool is None:
                        body = _loop_tool_error_payload(
                            "unknown_tool",
                            f"unknown tool {tool_name!r}",
                        )
                    else:
                        try:
                            raw = executor.dispatch_tool(
                                out,
                                flow_tool,
                                tc.function.arguments_parsed or {},
                            )
                            body = _summarize_dispatch_result(flow_tool, raw)
                        except Exception as exc:
                            logger.exception(
                                "tool invocation failed for tool=%s", tool_name
                            )
                            body = _loop_tool_error_payload(
                                "tool_execution_exception",
                                f"{type(exc).__name__}: {exc}",
                                detail=type(exc).__name__,
                            )
                rows_list.append(tool_feedback_chunk(tc.id, tool_name, body))
                _sync_loop_out_rows(out, rows_list)
                _notify_chunk_append(chunk_print, rows_list, out)
            continue

        rows_list.append(assistant_turn_chunk(tool_calls=None, content=msg.content))
        _sync_loop_out_rows(out, rows_list)
        _notify_chunk_append(chunk_print, rows_list, out)
        if choice.finish_reason in ("stop", "length", "content_filter"):
            break
    else:
        # Loop exhausted max_tool_rounds without a natural finish_reason.
        # The last row may be a tool_result, which is easy to mistake for
        # a mid-run failure. Warn and stamp lineage so callers can detect
        # truncation programmatically.
        logger.warning(
            "run_session_loop hit max_tool_rounds=%d without "
            "finish_reason in (stop, length, content_filter); "
            "last row may be a tool_result",
            max_tool_rounds,
        )
        out.lineage_extras = out.lineage_extras + (("loop.truncated", True),)

    out.chunk_table = ChunkTable(rows=tuple(rows_list))
    reg.set_active(out)
    return out


__all__ = [
    "ChunkAppendHook",
    "ChunkPrintFn",
    "SessionLoopExecutor",
    "ensure_stdio_utf8",
    "sink_chunk_print",
    "run_session_loop",
]
