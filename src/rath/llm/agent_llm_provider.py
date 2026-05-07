"""Sampling / routing options folded into Rath LLM chat requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, kw_only=True, slots=True)
class AgentLLMProvider:
    """OpenAI-style kwargs for ``run_session_loop`` (no ``messages`` / ``tools``).

    Same wire fields as :class:`~rath.llm.chat_request.RathLLMChatRequest`,
    excluding those the loop sets.
    """

    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_completion_tokens: int | None = None
    max_tokens: int | None = None
    stop: str | list[str] | None = None
    n: int | None = None
    seed: int | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    tool_choice: Any | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict[str, Any] | None = None
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


__all__ = ["AgentLLMProvider"]
