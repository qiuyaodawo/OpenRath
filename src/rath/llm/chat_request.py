"""Frozen request types for OpenAI-compatible chat completions."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

__all__ = [
    "RathLLMMessage",
    "RathLLMFunctionTool",
    "RathLLMChatRequest",
]

RathLLMRole = Literal["system", "user", "assistant", "tool", "developer"]


@dataclass(frozen=True, slots=True)
class RathLLMMessage:
    """One ``messages[]`` element for chat ``completions.create``.

    ``tool_calls`` is set only for assistant turns in tool-using conversations.
    """

    role: str
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[Mapping[str, Any], ...] | None = None


@dataclass(frozen=True, slots=True)
class RathLLMFunctionTool:
    """A function-style tool definition (``type: function``)."""

    name: str
    parameters: dict[str, Any]
    description: str | None = None
    strict: bool | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class RathLLMChatRequest:
    """Maps to keyword arguments passed to ``client.chat.completions.create``.

    ``model=None`` falls back to :attr:`~rath.llm.provider.Provider.model` on the
    client :class:`~rath.llm.provider.Provider` passed to
    :class:`~rath.llm.client.RathOpenAIChatClient`.
    """

    messages: tuple[RathLLMMessage, ...]
    model: str | None = None
    tools: tuple[RathLLMFunctionTool, ...] | None = None
    tool_choice: Any | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict[str, Any] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    n: int | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    logit_bias: dict[str, int] | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    reasoning_effort: str | None = None
    verbosity: str | None = None
    metadata: dict[str, str] | None = None
    user: str | None = None
    store: bool | None = None
    service_tier: str | None = None
    extra_create_args: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
