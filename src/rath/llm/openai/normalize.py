"""Normalize ``ChatCompletion`` SDK objects into Rath dataclasses."""

from __future__ import annotations

from typing import Any, Literal, Mapping, cast

from openai.types.chat import ChatCompletion

from rath.llm.chat_response import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.llm.tool_args import parse_tool_arguments

__all__ = ["normalize_chat_completion"]

_FINISH_REASONS = frozenset(
    {"stop", "length", "tool_calls", "content_filter", "function_call"}
)


def _coerce_finish_reason(value: str | None) -> RathLLMFinishReason:
    """Map API ``finish_reason``; unknown vendor values become ``stop``."""
    if value in _FINISH_REASONS:
        return cast(RathLLMFinishReason, value)
    return "stop"


def _normalize_tool_calls(
    raw_list: list[Mapping[str, Any]] | None,
) -> tuple[RathLLMToolCallPart, ...] | None:
    if not raw_list:
        return None
    parts: list[RathLLMToolCallPart] = []
    for raw in raw_list:
        fn_raw = raw.get("function")
        if not isinstance(fn_raw, dict):
            fn_raw = {}
        name = str(fn_raw.get("name") or "")
        arg_str = str(fn_raw.get("arguments") or "")
        parsed, perr = parse_tool_arguments(arg_str)
        parts.append(
            RathLLMToolCallPart(
                id=str(raw.get("id") or ""),
                type=str(raw.get("type") or "function"),
                function=RathLLMToolCallFunction(
                    name=name,
                    arguments=arg_str,
                    arguments_parsed=parsed,
                    arguments_parse_error=perr,
                ),
            )
        )
    return tuple(parts)


def _str_or_none(val: Any) -> str | None:
    if val is None or isinstance(val, str):
        return val
    return None


def _normalize_assistant_message(
    msg: Mapping[str, Any],
) -> RathLLMAssistantMessage:
    tc_raw = msg.get("tool_calls")
    if isinstance(tc_raw, list):
        tool_calls = _normalize_tool_calls(cast(list[Mapping[str, Any]], tc_raw))
    else:
        tool_calls = _normalize_tool_calls(None)
    annotations = msg.get("annotations")
    ann_tuple: tuple[Mapping[str, Any], ...] | None = None
    if isinstance(annotations, list):
        ann_tuple = tuple(
            cast(Mapping[str, Any], a) for a in annotations if isinstance(a, dict)
        )
    fc = msg.get("function_call")
    fc_map: Mapping[str, Any] | None = None
    if isinstance(fc, dict):
        fc_map = cast(Mapping[str, Any], fc)
    rc = msg.get("reasoning_content")
    reasoning = rc if isinstance(rc, str) else None
    return RathLLMAssistantMessage(
        role="assistant",
        content=_str_or_none(msg.get("content")),
        refusal=_str_or_none(msg.get("refusal")),
        reasoning_content=reasoning,
        tool_calls=tool_calls,
        function_call=fc_map,
        annotations=ann_tuple,
    )


def normalize_chat_completion(completion: ChatCompletion) -> RathLLMChatResponse:
    """Convert an SDK ``ChatCompletion`` into :class:`RathLLMChatResponse`."""
    raw = completion.model_dump(mode="json")

    choices_out: list[RathLLMChatChoice] = []
    for ch in raw.get("choices") or []:
        if not isinstance(ch, dict):
            continue
        msg = ch.get("message")
        if not isinstance(msg, dict):
            msg = {}
        finish = _coerce_finish_reason(
            ch.get("finish_reason")
            if isinstance(ch.get("finish_reason"), str)
            else None
        )
        logprobs = ch.get("logprobs")
        lp: Mapping[str, Any] | None = None
        if isinstance(logprobs, dict):
            lp = cast(Mapping[str, Any], logprobs)
        choices_out.append(
            RathLLMChatChoice(
                index=int(ch.get("index", 0)),
                finish_reason=finish,
                message=_normalize_assistant_message(msg),
                logprobs=lp,
            )
        )

    usage_out: RathLLMTokenUsage | None = None
    u = raw.get("usage")
    if isinstance(u, dict):
        usage_out = RathLLMTokenUsage(
            prompt_tokens=int(u.get("prompt_tokens", 0)),
            completion_tokens=int(u.get("completion_tokens", 0)),
            total_tokens=int(u.get("total_tokens", 0)),
            completion_tokens_details=cast(
                Mapping[str, Any] | None,
                u.get("completion_tokens_details")
                if isinstance(u.get("completion_tokens_details"), dict)
                else None,
            ),
            prompt_tokens_details=cast(
                Mapping[str, Any] | None,
                u.get("prompt_tokens_details")
                if isinstance(u.get("prompt_tokens_details"), dict)
                else None,
            ),
        )

    object_type: Literal["chat.completion"] = "chat.completion"

    return RathLLMChatResponse(
        id=str(raw.get("id") or ""),
        choices=tuple(choices_out),
        created=int(raw.get("created") or 0),
        model=str(raw.get("model") or ""),
        object_type=object_type,
        service_tier=raw.get("service_tier")
        if isinstance(raw.get("service_tier"), str)
        else None,
        system_fingerprint=raw.get("system_fingerprint")
        if isinstance(raw.get("system_fingerprint"), str)
        else None,
        usage=usage_out,
        raw=cast(Mapping[str, Any], raw),
    )
