"""Translate Anthropic messages-API requests and responses to OpenRath shapes.

Two pure functions are exposed:

  - :func:`build_anthropic_kwargs` rewrites a :class:`RathLLMChatRequest`
    (OpenAI-style messages, OpenAI-style tools) into the kwargs that
    :meth:`anthropic.Anthropic.messages.create` expects.
  - :func:`normalize_anthropic_response` re-maps the Anthropic ``Message``
    response back into a :class:`RathLLMChatResponse` so the rest of the
    session loop keeps the same dataclasses.

The conversion is intentionally lossy on a few axes:

  - Anthropic enforces a single ``system`` field; all OpenAI ``role=system``
    messages are concatenated (\\n\\n joined) into one.
  - OpenAI ``role=tool`` messages become Anthropic ``user`` messages with a
    ``tool_result`` content block keyed by ``tool_call_id``.
  - Anthropic tool-use content blocks become OpenAI-style ``tool_calls`` with
    a JSON-encoded ``arguments`` string so :class:`RathLLMToolCallPart` keeps
    its existing shape.
  - Stop-reason mapping is opinionated: ``end_turn`` -> ``stop``,
    ``max_tokens`` -> ``length``, ``tool_use`` -> ``tool_calls``,
    ``stop_sequence`` -> ``stop``; anything else collapses to ``stop``.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, cast

from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import (
    RathLLMAssistantMessage,
    RathLLMChatChoice,
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMTokenUsage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)

__all__ = [
    "build_anthropic_kwargs",
    "normalize_anthropic_response",
]


# Fallback ``max_tokens`` for Anthropic's required field when neither the
# request nor the provider set one. Deliberately conservative - current Claude
# models accept far more, but a low default avoids accidentally racking up
# token bills on a stray call. Callers that need long outputs should set
# ``RathLLMChatRequest.max_tokens`` (or ``max_completion_tokens``) explicitly.
_DEFAULT_MAX_TOKENS = 4096


def _coerce_text(content: Any) -> str:
    """Anthropic ``user`` / ``system`` content must be plain string for our use.

    OpenAI allows content lists (multi-part); to keep the adapter simple this
    PR only handles ``str`` and joins anything else with ``str()``.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(part) for part in content)
    return str(content)


def _tool_choice_for_anthropic(tc: Any) -> Any:
    """Map OpenAI ``tool_choice`` to Anthropic shape; pass through dicts."""
    if tc is None or tc == "auto" or tc == "":
        return None
    if tc == "none":
        return {"type": "none"}
    if tc == "required":
        return {"type": "any"}
    if isinstance(tc, dict):
        if tc.get("type") == "function":
            fn = tc.get("function", {})
            name = fn.get("name")
            if name:
                return {"type": "tool", "name": name}
        return tc
    return None


def _tools_for_anthropic(
    tools: tuple[Any, ...] | None,
) -> list[dict[str, Any]] | None:
    if not tools:
        return None
    out: list[dict[str, Any]] = []
    for t in tools:
        params = dict(t.parameters or {"type": "object", "properties": {}})
        entry: dict[str, Any] = {
            "name": t.name,
            "input_schema": params,
        }
        if t.description is not None:
            entry["description"] = t.description
        out.append(entry)
    return out


def build_anthropic_kwargs(
    req: RathLLMChatRequest,
    *,
    default_model: str | None,
) -> dict[str, Any]:
    """Translate :class:`RathLLMChatRequest` into ``messages.create`` kwargs.

    ``default_model`` mirrors :func:`~rath.llm.openai_create_kwargs.to_create_kwargs`:
    it's used when neither the request nor the provider supplies a model name.
    """
    model = req.model or default_model
    if not model:
        raise ValueError(
            "model is required: set RathLLMChatRequest.model or Provider.model",
        )

    system_parts: list[str] = []
    messages: list[dict[str, Any]] = []
    for m in req.messages:
        if m.role == "system" or m.role == "developer":
            system_parts.append(_coerce_text(m.content))
            continue
        if m.role == "tool":
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": _coerce_text(m.content),
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": _coerce_text(m.content)})
            for tc in m.tool_calls:
                fn = tc.get("function") or {}
                arg_str = fn.get("arguments") or "{}"
                try:
                    parsed = json.loads(arg_str) if arg_str else {}
                except json.JSONDecodeError:
                    parsed = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": fn.get("name", ""),
                        "input": parsed,
                    }
                )
            messages.append({"role": "assistant", "content": blocks})
            continue
        # plain user / assistant text
        messages.append(
            {
                "role": m.role if m.role in ("user", "assistant") else "user",
                "content": _coerce_text(m.content),
            }
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": req.max_tokens or req.max_completion_tokens or _DEFAULT_MAX_TOKENS,
    }
    if system_parts:
        kwargs["system"] = "\n\n".join(p for p in system_parts if p)
    if req.temperature is not None:
        kwargs["temperature"] = req.temperature
    if req.top_p is not None:
        kwargs["top_p"] = req.top_p
    if req.stop is not None:
        kwargs["stop_sequences"] = (
            [req.stop] if isinstance(req.stop, str) else list(req.stop)
        )
    if req.metadata is not None:
        kwargs["metadata"] = req.metadata
    tools = _tools_for_anthropic(req.tools)
    if tools is not None:
        kwargs["tools"] = tools
    tool_choice = _tool_choice_for_anthropic(req.tool_choice)
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice

    extra = dict(req.extra_create_args)
    extra.pop("stream", None)  # streaming is a separate path
    kwargs.update(extra)
    return kwargs


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
