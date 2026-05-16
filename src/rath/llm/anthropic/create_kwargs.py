"""Translate :class:`RathLLMChatRequest` into ``Anthropic.messages.create`` kwargs.

The conversion is intentionally lossy on a few axes:

  - Anthropic enforces a single ``system`` field; all OpenAI ``role=system``
    messages are concatenated (\\n\\n joined) into one.
  - OpenAI ``role=tool`` messages become Anthropic ``user`` messages with a
    ``tool_result`` content block keyed by ``tool_call_id``.
  - Anthropic tool-use content blocks become OpenAI-style ``tool_calls`` with
    a JSON-encoded ``arguments`` string in the matching response normalizer.
"""

from __future__ import annotations

import json
from typing import Any

from rath.llm.chat_request import RathLLMChatRequest

__all__ = ["build_anthropic_kwargs", "DEFAULT_MAX_TOKENS"]


# Fallback ``max_tokens`` for Anthropic's required field when neither the
# request nor the provider set one. Deliberately conservative - current Claude
# models accept far more, but a low default avoids accidentally racking up
# token bills on a stray call. Callers that need long outputs should set
# ``RathLLMChatRequest.max_tokens`` (or ``max_completion_tokens``) explicitly.
DEFAULT_MAX_TOKENS = 4096


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

    ``default_model`` mirrors :func:`~rath.llm.openai.create_kwargs.to_create_kwargs`:
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
        "max_tokens": req.max_tokens or req.max_completion_tokens or DEFAULT_MAX_TOKENS,
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
