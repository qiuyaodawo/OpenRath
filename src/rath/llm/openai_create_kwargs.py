"""Build keyword arguments for ``OpenAI().chat.completions.create``."""

from __future__ import annotations

from typing import Any

from rath.llm.chat_request import (
    RathLLMChatRequest,
    RathLLMFunctionTool,
    RathLLMMessage,
)

__all__ = ["to_create_kwargs"]


def _message_as_openai_dict(message: RathLLMMessage) -> dict[str, Any]:
    d: dict[str, Any] = {"role": message.role}
    if message.content is not None:
        d["content"] = message.content
    if message.name is not None:
        d["name"] = message.name
    if message.tool_call_id is not None:
        d["tool_call_id"] = message.tool_call_id
    if message.tool_calls is not None:
        d["tool_calls"] = [dict(tc) for tc in message.tool_calls]
    return d


def _drop_additional_properties(obj: Any) -> Any:
    """Recursively drop ``additionalProperties`` keys from nested dict/list schema."""

    if isinstance(obj, dict):
        return {
            k: _drop_additional_properties(v)
            for k, v in obj.items()
            if k != "additionalProperties"
        }
    if isinstance(obj, list):
        return [_drop_additional_properties(x) for x in obj]
    return obj


def _function_tool_as_openai_dict(tool: RathLLMFunctionTool) -> dict[str, Any]:
    params = _drop_additional_properties(dict(tool.parameters))
    fn: dict[str, Any] = {
        "name": tool.name,
        "parameters": params,
    }
    if tool.description is not None:
        fn["description"] = tool.description
    if tool.strict is not None:
        fn["strict"] = tool.strict
    return {"type": "function", "function": fn}


def to_create_kwargs(
    req: RathLLMChatRequest,
    *,
    default_model: str | None,
) -> dict[str, Any]:
    """Map :class:`RathLLMChatRequest` to ``OpenAI.chat.completions.create`` kwargs.

    Non-streaming only: ``stream`` is forced to ``False`` after
    ``extra_create_args`` are merged. ``stream=True`` in extras raises
    ``ValueError``.
    """
    model = req.model or default_model
    if not model:
        raise ValueError(
            "model is required: set RathLLMChatRequest.model or Provider.model",
        )
    out: dict[str, Any] = {
        "model": model,
        "messages": [_message_as_openai_dict(m) for m in req.messages],
    }

    if req.tools is not None:
        out["tools"] = [_function_tool_as_openai_dict(t) for t in req.tools]
    if req.tool_choice is not None:
        out["tool_choice"] = req.tool_choice
    if req.parallel_tool_calls is not None:
        out["parallel_tool_calls"] = req.parallel_tool_calls
    if req.response_format is not None:
        out["response_format"] = req.response_format
    if req.temperature is not None:
        out["temperature"] = req.temperature
    if req.top_p is not None:
        out["top_p"] = req.top_p
    if req.max_completion_tokens is not None:
        out["max_completion_tokens"] = req.max_completion_tokens
    if req.max_tokens is not None:
        out["max_tokens"] = req.max_tokens
    if req.stop is not None:
        out["stop"] = req.stop
    if req.n is not None:
        out["n"] = req.n
    if req.seed is not None:
        out["seed"] = req.seed
    if req.frequency_penalty is not None:
        out["frequency_penalty"] = req.frequency_penalty
    if req.presence_penalty is not None:
        out["presence_penalty"] = req.presence_penalty
    if req.logit_bias is not None:
        out["logit_bias"] = req.logit_bias
    if req.logprobs is not None:
        out["logprobs"] = req.logprobs
    if req.top_logprobs is not None:
        out["top_logprobs"] = req.top_logprobs
    if req.reasoning_effort is not None:
        out["reasoning_effort"] = req.reasoning_effort
    if req.verbosity is not None:
        out["verbosity"] = req.verbosity
    if req.metadata is not None:
        out["metadata"] = req.metadata
    if req.user is not None:
        out["user"] = req.user
    if req.store is not None:
        out["store"] = req.store
    if req.service_tier is not None:
        out["service_tier"] = req.service_tier

    extra = dict(req.extra_create_args)
    if extra.pop("stream", None) is True:
        raise ValueError(
            "stream=True is not supported (only non-streaming completions "
            "are implemented)",
        )
    out.update(extra)
    out["stream"] = False
    return out
