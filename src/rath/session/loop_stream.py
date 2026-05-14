"""Streaming counterpart to :func:`~rath.session.loop.run_session_loop`.

Opt-in entry point that emits :class:`~rath.llm.RathLLMStreamDelta` events
through an ``on_event`` callback while the assistant message is being
generated, then reuses the non-streaming loop's tool-dispatch machinery for
the rest of the round.

Chunk-level atomicity is preserved: deltas are folded into one
``RathLLMChatResponse`` before the loop appends to ``out.chunk_table``, so
forks / lineage / token accounting all see complete messages.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Iterator, Protocol, runtime_checkable

from rath.flow.tool import FlowToolCall
from rath.llm import (
    Provider,
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatRequest,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMStreamDelta,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.session.loop import (
    ChunkAppendHook,
    SessionLoopExecutor,
    _build_default_client,
    run_session_loop,
)
from rath.session.provider_builtin import DefaultSessionLoopExecutor
from rath.session.session import Session

__all__ = [
    "accumulate_stream_to_response",
    "run_session_loop_stream",
    "StreamingChatClient",
]


@runtime_checkable
class StreamingChatClient(Protocol):
    """Minimal Protocol for clients with ``complete_stream``.

    The :class:`~rath.llm.RathOpenAIChatClient` already exposes
    ``complete_stream``; callers passing custom clients only need the same
    method signature.
    """

    def complete_stream(
        self, req: RathLLMChatRequest
    ) -> Iterator[RathLLMStreamDelta]: ...


def accumulate_stream_to_response(
    deltas: Any,  # Iterable[RathLLMStreamDelta]
    *,
    on_event: Callable[[RathLLMStreamDelta], None] | None = None,
    response_id: str = "",
    model: str = "",
) -> RathLLMChatResponse:
    """Fold an iterable of stream deltas into one :class:`RathLLMChatResponse`.

    Each delta is forwarded to ``on_event`` immediately so callers can drive a
    streaming UI; the final accumulated message is then returned for the
    session loop to append to its chunk_table as a single atomic chunk.
    """
    text_parts: list[str] = []
    # tool_call accumulation keyed by index
    tool_buckets: dict[int, dict[str, Any]] = {}
    finish: RathLLMFinishReason | None = None
    usage: RathLLMTokenUsage | None = None

    for d in deltas:
        if on_event is not None:
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
            parsed: dict[str, Any] | None
            parse_error: bool
            if arg_str:
                try:
                    parsed_val = json.loads(arg_str)
                    if isinstance(parsed_val, dict):
                        parsed, parse_error = parsed_val, False
                    else:
                        parsed, parse_error = None, True
                except (ValueError, TypeError):
                    parsed, parse_error = None, True
            else:
                parsed, parse_error = None, False
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
        id=response_id,
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


class _StreamingExecutorAdapter:
    """Wrap a streaming client + on_event callback as a SessionLoopExecutor.

    The session loop calls ``complete`` once per round; this adapter consumes
    the underlying client's ``complete_stream``, forwards each delta to
    ``on_event``, and returns the accumulated :class:`RathLLMChatResponse`.
    """

    __slots__ = ("_client", "_on_event", "_inner_executor")

    def __init__(
        self,
        client: Any,
        on_event: Callable[[RathLLMStreamDelta], None] | None,
        inner_executor: SessionLoopExecutor | None = None,
    ) -> None:
        self._client = client
        self._on_event = on_event
        self._inner_executor = inner_executor or DefaultSessionLoopExecutor(client)

    @property
    def provider(self) -> Provider:
        return self._client.provider  # type: ignore[no-any-return]

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        if not hasattr(self._client, "complete_stream"):
            raise TypeError(
                "client passed to run_session_loop_stream must expose "
                "complete_stream(req) -> Iterator[RathLLMStreamDelta]",
            )
        return accumulate_stream_to_response(
            self._client.complete_stream(req),
            on_event=self._on_event,
            model=getattr(self._client.provider, "model", "") or "",
        )

    def dispatch_tool(
        self, session: Session, tool: FlowToolCall, arguments: Any
    ) -> Any:
        return self._inner_executor.dispatch_tool(session, tool, arguments)

    def tool_schemas(self) -> Any:
        return self._inner_executor.tool_schemas()


def run_session_loop_stream(
    user_session: Session,
    agent_session: Session,
    *,
    agent_provider: Provider,
    tools: list[FlowToolCall] | None = None,
    client: Any = None,
    max_tool_rounds: int = 16,
    on_event: Callable[[RathLLMStreamDelta], None] | None = None,
    chunk_print: ChunkAppendHook | None = None,
) -> Session:
    """Run a session loop, streaming each assistant chunk through ``on_event``.

    Same semantics as :func:`~rath.session.loop.run_session_loop` for tool
    dispatch, lineage, and token / budget accounting. The difference is per-
    delta visibility: ``on_event(delta)`` is invoked for every
    :class:`RathLLMStreamDelta` as the assistant message streams in.

    ``client`` is any object with a ``complete_stream(req)`` method (typically
    :class:`~rath.llm.RathOpenAIChatClient`). When omitted it is built from
    ``agent_provider`` using the same dispatch as the non-streaming loop.

    Streaming for ``provider_kind="anthropic"`` is **not** implemented in this
    PR: rather than build an Anthropic client that lacks ``complete_stream``
    and only fail mid-loop (after sessions are stamped and lineage written),
    this entrypoint refuses the combination upfront with a clear error. Pass
    an explicit ``client=`` to override - e.g. a custom Anthropic streaming
    adapter once one exists.
    """
    if client is None:
        if agent_provider.provider_kind == "anthropic":
            raise NotImplementedError(
                "streaming + provider_kind='anthropic' is not implemented; "
                "use the OpenAI provider for streaming today, or pass an "
                "explicit client= with a complete_stream(req) method.",
            )
        client = _build_default_client(agent_provider)
    adapter = _StreamingExecutorAdapter(client, on_event)
    return run_session_loop(
        user_session,
        agent_session,
        agent_provider=agent_provider,
        tools=tools,
        executor=adapter,
        max_tool_rounds=max_tool_rounds,
        chunk_print=chunk_print,
    )
