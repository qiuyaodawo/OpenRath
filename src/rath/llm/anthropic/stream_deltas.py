"""Map Anthropic Messages API stream events to :class:`RathLLMStreamDelta`."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

from rath.llm.anthropic.normalize import _stop_reason_to_finish
from rath.llm.chat_response import RathLLMStreamDelta, RathLLMTokenUsage

__all__ = ["anthropic_event_to_deltas"]


def _event_payload(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return cast(dict[str, Any], event.model_dump(mode="json"))
    if isinstance(event, dict):
        return event
    etype = getattr(event, "type", None)
    return {"type": etype} if etype else {}


def anthropic_event_to_deltas(event: Any) -> Iterator[RathLLMStreamDelta]:
    """Translate one Anthropic stream event into zero or more deltas."""
    payload = _event_payload(event)
    etype = payload.get("type")
    if etype == "content_block_delta":
        delta = payload.get("delta") or {}
        if delta.get("type") == "text_delta":
            text = delta.get("text")
            if isinstance(text, str) and text:
                yield RathLLMStreamDelta(content_delta=text)
        elif delta.get("type") == "input_json_delta":
            partial = delta.get("partial_json")
            if isinstance(partial, str) and partial:
                idx = payload.get("index")
                yield RathLLMStreamDelta(
                    tool_call_index=int(idx) if isinstance(idx, int) else 0,
                    tool_call_args_delta=partial,
                )
    elif etype == "content_block_start":
        block = payload.get("content_block") or {}
        if block.get("type") == "tool_use":
            idx = payload.get("index")
            yield RathLLMStreamDelta(
                tool_call_index=int(idx) if isinstance(idx, int) else 0,
                tool_call_id=str(block.get("id") or ""),
                tool_call_name_delta=str(block.get("name") or ""),
            )
    elif etype == "message_delta":
        mdelta = payload.get("delta") or {}
        stop = mdelta.get("stop_reason")
        if isinstance(stop, str):
            finish = _stop_reason_to_finish(stop)
            yield RathLLMStreamDelta(finish_reason=finish)
        usage = mdelta.get("usage") or {}
        if isinstance(usage, dict):
            prompt = int(usage.get("input_tokens", 0) or 0)
            completion = int(usage.get("output_tokens", 0) or 0)
            if prompt or completion:
                yield RathLLMStreamDelta(
                    usage=RathLLMTokenUsage(
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=prompt + completion,
                    )
                )
