"""Session loop: alternate LLM completions with sandbox tool execution.

The single public entry point :func:`run_session_loop` drives a multi-turn
assistant pass. Two optional parameters extend it:

* ``on_event`` — receives one :class:`~rath.llm.RathLLMStreamDelta` per
  streamed chunk. Requires the resolved chat client to satisfy
  :class:`~rath.llm.StreamingChatClient` (Anthropic does not currently). When
  ``on_event`` is ``None`` (the default), the loop runs non-streaming.

* ``persist`` / ``persist_path`` — when truthy, the loop holds a
  :class:`~rath.session.persistence.SessionWriter` internally and appends each
  new chunk to ``.openrath/sessions/<out.id>.jsonl`` (or to ``persist_path``).
  The writer's trailer is written on graceful return; on exception the file
  is left without a trailer (``closed=False`` on reload — the crash signal).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable

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
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMFunctionTool,
    RathLLMStreamDelta,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
    StreamingChatClient,
    add_usage,
    chat_client_for,
)
from rath.llm.tool_args import parse_tool_arguments
from rath.session.chat_request_build import provider_into_chat_request
from rath.session.chunk import (
    ChunkRow,
    ChunkTable,
    assistant_turn_chunk,
    chunk_table_to_messages,
    tool_feedback_chunk,
)
from rath.session.graph import LineageKind, LineageRecorder, SessionLineage
from rath.session.manager import session_registry
from rath.session.persistence import SessionWriter
from rath.session.provider_builtin import DefaultSessionLoopExecutor
from rath.session.session import Session
from rath.utils.decoding import decode_subprocess_output

logger = logging.getLogger(__name__)

OnEventCb = Callable[[RathLLMStreamDelta], None]
"""Type alias for the streaming-delta callback consumed by :func:`run_session_loop`."""


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


def _accumulate_stream_to_response(
    deltas: Any,
    *,
    on_event: Callable[[RathLLMStreamDelta], None],
    model: str = "",
) -> RathLLMChatResponse:
    """Fold an iterable of stream deltas into one :class:`RathLLMChatResponse`.

    Each delta is forwarded to ``on_event`` immediately so callers can drive a
    streaming UI; the final accumulated message is then returned for the
    session loop to append to its chunk_table as a single atomic chunk.
    """
    text_parts: list[str] = []
    tool_buckets: dict[int, dict[str, Any]] = {}
    finish: RathLLMFinishReason | None = None
    usage: RathLLMTokenUsage | None = None

    for d in deltas:
        on_event(d)
        if d.content_delta:
            text_parts.append(d.content_delta)
        if d.tool_call_index is not None or d.tool_call_id is not None:
            idx = d.tool_call_index if d.tool_call_index is not None else 0
            bucket = tool_buckets.setdefault(
                idx, {"id": "", "name": "", "arguments": ""}
            )
            if d.tool_call_id:
                bucket["id"] = d.tool_call_id
            if d.tool_call_name_delta:
                bucket["name"] = (bucket["name"] or "") + d.tool_call_name_delta
            if d.tool_call_args_delta:
                bucket["arguments"] = (
                    bucket["arguments"] or ""
                ) + d.tool_call_args_delta
        if d.finish_reason is not None:
            finish = d.finish_reason
        if d.usage is not None:
            usage = d.usage

    tool_calls: tuple[RathLLMToolCallPart, ...] | None = None
    if tool_buckets:
        parts: list[RathLLMToolCallPart] = []
        for _, bucket in sorted(tool_buckets.items()):
            arg_str = bucket.get("arguments") or ""
            parsed, parse_error = parse_tool_arguments(arg_str)
            parts.append(
                RathLLMToolCallPart(
                    id=str(bucket.get("id") or ""),
                    type="function",
                    function=RathLLMToolCallFunction(
                        name=str(bucket.get("name") or ""),
                        arguments=arg_str,
                        arguments_parsed=parsed,
                        arguments_parse_error=parse_error,
                    ),
                )
            )
        tool_calls = tuple(parts)

    content_text = "".join(text_parts) if text_parts else None
    if finish is None:
        finish = "tool_calls" if tool_calls else "stop"

    return RathLLMChatResponse(
        id="",
        choices=(
            RathLLMChatChoice(
                index=0,
                finish_reason=finish,
                message=RathLLMAssistantMessage(
                    role="assistant",
                    content=content_text,
                    tool_calls=tool_calls,
                ),
            ),
        ),
        created=0,
        model=model,
        usage=usage,
    )


class StreamingExecutor:
    """Adapt a :class:`StreamingChatClient` to the :class:`SessionLoopExecutor` protocol.

    ``complete()`` consumes the client's ``complete_stream(req)``, forwards
    each delta to ``on_event``, and returns the accumulated response. Tool
    dispatch and schema lookup are delegated to an inner executor (a fresh
    :class:`DefaultSessionLoopExecutor` wrapping the same client when one is
    not supplied).
    """

    __slots__ = ("client", "_on_event", "_inner")

    def __init__(
        self,
        client: StreamingChatClient,
        on_event: Callable[[RathLLMStreamDelta], None],
        inner: SessionLoopExecutor | None = None,
    ) -> None:
        self.client = client
        self._on_event = on_event
        self._inner = inner or DefaultSessionLoopExecutor(client)

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        return _accumulate_stream_to_response(
            self.client.complete_stream(req),
            on_event=self._on_event,
            model=getattr(self.client.provider, "model", "") or "",
        )

    def dispatch_tool(
        self, session: Session, tool: FlowToolCall, arguments: Mapping[str, Any]
    ) -> Any:
        return self._inner.dispatch_tool(session, tool, arguments)

    def tool_schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        return self._inner.tool_schemas()


def resolve_executor(
    *,
    agent_provider: Provider,
    executor: SessionLoopExecutor | None,
    on_event: OnEventCb | None,
) -> SessionLoopExecutor:
    """Pick the executor for ``run_session_loop`` / ``run_session_compress``.

    A caller-supplied ``executor`` is returned as-is (and is incompatible with
    ``on_event``). Otherwise a chat client is built from ``agent_provider`` —
    streaming when ``on_event`` is set, default otherwise.
    """
    if executor is not None and on_event is not None:
        raise ValueError(
            "on_event with a custom executor is not supported; "
            "wrap your client with StreamingExecutor and pass that as executor=."
        )
    if executor is not None:
        return executor
    client = chat_client_for(agent_provider)
    if on_event is not None:
        if not isinstance(client, StreamingChatClient):
            raise TypeError(
                "on_event requires a StreamingChatClient; "
                f"{type(client).__name__} (provider_kind="
                f"{agent_provider.provider_kind!r}) does not implement "
                "complete_stream(req). Drop on_event for non-streaming."
            )
        return StreamingExecutor(client, on_event)
    return DefaultSessionLoopExecutor(client)


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


def _append_and_persist(
    out: Session,
    rows_list: list[Any],
    row: ChunkRow,
    writer: SessionWriter | None,
) -> None:
    """Append ``row`` to ``rows_list`` (and JSONL if a writer is set).

    Does **not** rebuild ``out.chunk_table`` per row — the caller materialises
    once per assistant turn via :func:`_sync_loop_out_rows`, plus one final
    rebuild after the loop. This keeps the loop O(rounds) rather than the
    O(rows²) shape that comes from rebuilding the tuple on every append.
    """
    rows_list.append(row)
    if writer is not None:
        writer.write_chunk(len(rows_list) - 1, row)


def run_session_loop(
    user_session: Session,
    agent_session: Session,
    *,
    agent_provider: Provider,
    tools: list[FlowToolCall] | None = None,
    executor: SessionLoopExecutor | None = None,
    max_tool_rounds: int = 16,
    on_event: Callable[[RathLLMStreamDelta], None] | None = None,
    persist: bool = False,
    persist_path: Path | None = None,
    sandbox_handle_id: str | None = None,
) -> Session:
    """Run one multi-turn assistant pass with optional tool rounds.

    Built-in tools come from :func:`~rath.flow.tool.global_system_tools`; pass
    instantiated :class:`~rath.flow.tool.FlowToolCall` objects in ``tools`` to
    add or override. Shadowing built-in names is disallowed.

    Shares the ``BackendSandbox`` from ``user_session`` with the returned
    session (refcount + 1); the user session keeps its reference and either
    side can :meth:`Session.close_sandbox` independently. LLM routing kwargs
    come from ``agent_provider``; completions and tool dispatch go through
    ``executor`` (a fresh :class:`DefaultSessionLoopExecutor` is built when
    omitted).

    When ``on_event`` is provided, completions stream — the resolved client
    must satisfy :class:`~rath.llm.StreamingChatClient`, otherwise a
    :class:`TypeError` is raised before any session is registered. Each
    :class:`RathLLMStreamDelta` is forwarded to ``on_event``; chunks are still
    appended atomically (one accumulated assistant message per round).

    When ``persist`` is true or ``persist_path`` is given, every appended row
    is written to ``.openrath/sessions/<out.id>.jsonl`` (or to
    ``persist_path``). On graceful return the trailer is written; on
    exception the file is abandoned without a trailer.

    Message assembly concatenates ``agent_session.chunk_table`` ahead of the
    user rows for the LLM; head rows stay out of ``out.chunk_table``.
    """

    table = merge_tools_for_loop(tools)

    executor = resolve_executor(
        agent_provider=agent_provider, executor=executor, on_event=on_event
    )

    prefs = agent_provider

    rows_list: list[Any] = list(user_session.chunk_table.rows)
    out = Session(
        chunk_table=ChunkTable(rows=tuple(rows_list)),
        sandbox_backend=user_session.sandbox_backend,
        _sandbox_open_spec=user_session._sandbox_open_spec,
        lineage=SessionLineage(
            producer_user_session_id=user_session.id,
            producer_system_session_id=agent_session.id,
        ),
    )
    if user_session.sandbox is not None and not user_session.sandbox.closed:
        out.bind_sandbox(user_session.sandbox)
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

    writer: SessionWriter | None = None
    if persist or persist_path is not None:
        writer = SessionWriter(
            out,
            sandbox_handle_id=sandbox_handle_id,
            path=persist_path,
        )
        # Seed the JSONL with any rows inherited from the user session so the
        # persisted transcript matches ``out.chunk_table`` exactly.
        for seed_index, seed_row in enumerate(rows_list):
            writer.write_chunk(seed_index, seed_row)

    tool_schemas = executor.tool_schemas()
    if not tool_schemas:
        tool_schemas = tools_dict_to_schemas(table)

    try:
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
                _append_and_persist(
                    out,
                    rows_list,
                    assistant_turn_chunk(tool_calls=tcalls, content=msg.content),
                    writer,
                )
                # Sync once per assistant turn so any tool that inspects
                # ``out.chunk_table`` during dispatch sees the message it is
                # answering. Per-tool-result rows are not synced individually
                # — the final rebuild at the bottom of the function picks
                # them up.
                _sync_loop_out_rows(out, rows_list)
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
                                "or unparseable arguments"
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
                    _append_and_persist(
                        out,
                        rows_list,
                        tool_feedback_chunk(tc.id, tool_name, body),
                        writer,
                    )
                continue

            _append_and_persist(
                out,
                rows_list,
                assistant_turn_chunk(tool_calls=None, content=msg.content),
                writer,
            )
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
    except BaseException:
        if writer is not None:
            writer.abandon()
        raise

    if writer is not None:
        writer.close()

    out.chunk_table = ChunkTable(rows=tuple(rows_list))
    reg.set_active(out)
    return out


__all__ = [
    "OnEventCb",
    "SessionLoopExecutor",
    "StreamingExecutor",
    "run_session_loop",
]
