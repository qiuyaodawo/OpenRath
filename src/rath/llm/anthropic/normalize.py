"""Normalize Anthropic ``Message`` payloads into :class:`RathLLMChatResponse`.

Stop-reason mapping is opinionated: ``end_turn`` -> ``stop``,
``max_tokens`` -> ``length``, ``tool_use`` -> ``tool_calls``,
``stop_sequence`` -> ``stop``; anything else collapses to ``stop``.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, cast

from rath.llm.chat_response import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)

__all__ = ["normalize_anthropic_response"]


_STOP_REASON_MAP: dict[str, RathLLMFinishReason] = {
    "end_turn": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "stop_sequence": "stop",
}


def _stop_reason_to_finish(value: str | None) -> RathLLMFinishReason:
    return _STOP_REASON_MAP.get(value or "", "stop")


def _content_to_message(
    content: list[Mapping[str, Any]],
) -> tuple[str | None, tuple[RathLLMToolCallPart, ...] | None]:
    """Split Anthropic content blocks into (text, tool_calls)."""
    text_parts: list[str] = []
    tool_calls: list[RathLLMToolCallPart] = []
    for block in content:
        btype = block.get("type")
        if btype == "text":
            text = block.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        elif btype == "tool_use":
            inp = block.get("input") or {}
            try:
                arg_str = json.dumps(inp, ensure_ascii=False)
            except (TypeError, ValueError):
                arg_str = "{}"
                inp = {}
            tool_calls.append(
                RathLLMToolCallPart(
                    id=str(block.get("id") or ""),
                    type="function",
                    function=RathLLMToolCallFunction(
                        name=str(block.get("name") or ""),
                        arguments=arg_str,
                        arguments_parsed=cast(dict[str, Any], inp)
                        if isinstance(inp, dict)
                        else None,
                        arguments_parse_error=False,
                    ),
                )
            )
    content_text = "\n".join(text_parts) if text_parts else None
    return content_text, (tuple(tool_calls) if tool_calls else None)


def normalize_anthropic_response(payload: Mapping[str, Any]) -> RathLLMChatResponse:
    """Map an Anthropic ``Message``-shaped dict to :class:`RathLLMChatResponse`.

    ``payload`` is expected to be the result of ``message.model_dump(mode='json')``
    on the SDK return value (or an equivalent fixture dict). Defending via
    dict lookups keeps the adapter compatible across minor SDK upgrades.
    """
    raw_content = payload.get("content") or []
    if not isinstance(raw_content, list):
        raw_content = []
    text, tool_calls = _content_to_message(raw_content)

    msg = RathLLMAssistantMessage(
        role="assistant",
        content=text,
        tool_calls=tool_calls,
    )
    finish = _stop_reason_to_finish(payload.get("stop_reason"))
    choice = RathLLMChatChoice(
        index=0,
        finish_reason=finish,
        message=msg,
    )

    usage = payload.get("usage") or {}
    usage_out: RathLLMTokenUsage | None = None
    if isinstance(usage, dict):
        prompt = int(usage.get("input_tokens", 0) or 0)
        completion = int(usage.get("output_tokens", 0) or 0)
        if prompt or completion:
            usage_out = RathLLMTokenUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
            )

    return RathLLMChatResponse(
        id=str(payload.get("id") or ""),
        choices=(choice,),
        created=0,  # Anthropic responses don't include a unix-timestamp ``created`` field
        model=str(payload.get("model") or ""),
        usage=usage_out,
        raw=payload,
    )
