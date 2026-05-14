"""Synchronous Anthropic chat client (thin SDK wrapper).

Mirrors :class:`~rath.llm.RathOpenAIChatClient`: same Protocol, same retry
behavior, same Provider fields. Translation between OpenRath's request /
response dataclasses and the Anthropic messages API happens in
:mod:`rath.llm.anthropic_normalize` (pure functions, fixture-testable).

Empty :attr:`Provider.api_key` falls back to ``ANTHROPIC_API_KEY``; empty
``base_url`` falls back to ``ANTHROPIC_BASE_URL``.
"""

from __future__ import annotations

import os
from typing import Any

from rath.llm._retry import retry_with_backoff
from rath.llm.anthropic_normalize import (
    build_anthropic_kwargs,
    normalize_anthropic_response,
)
from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse
from rath.llm.provider import Provider

from anthropic import (
    Anthropic,
    APIConnectionError as _AnthropicAPIConnectionError,
    APITimeoutError as _AnthropicAPITimeoutError,
    InternalServerError as _AnthropicInternalServerError,
    RateLimitError as _AnthropicRateLimitError,
)

_ANTHROPIC_RETRYABLE: tuple[type[BaseException], ...] = (
    _AnthropicRateLimitError,
    _AnthropicAPIConnectionError,
    _AnthropicAPITimeoutError,
    _AnthropicInternalServerError,
)


__all__ = ["RathAnthropicChatClient"]


class RathAnthropicChatClient:
    """Thin client around ``anthropic.Anthropic().messages.create`` (non-streaming)."""

    def __init__(self, provider: Provider) -> None:
        key = (provider.api_key or os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set and Provider.api_key is empty; "
                "either pass api_key= to Provider(...) or export "
                "ANTHROPIC_API_KEY (e.g. via a project .env file).",
            )
        self._provider = provider
        init_kw: dict[str, Any] = {"api_key": key}
        bu = (
            provider.base_url
            or os.environ.get("ANTHROPIC_BASE_URL")
            or ""
        ).strip()
        if bu:
            init_kw["base_url"] = bu
        self._client = Anthropic(**init_kw)

    @property
    def provider(self) -> Provider:
        return self._provider

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run ``messages.create`` and normalize the response.

        Transient errors are retried per :attr:`Provider.retry_max_attempts` /
        :attr:`Provider.retry_base_seconds`. The retry helper recognises
        OpenAI's exception classes by default; this client widens the
        retryable set via ``extra_retryable=`` to include the matching
        ``anthropic.*`` siblings (``RateLimitError``, ``APIConnectionError``,
        ``APITimeoutError``, ``InternalServerError``).
        """
        default_model = (
            self._provider.model or os.environ.get("ANTHROPIC_DEFAULT_MODEL")
        )
        kwargs = build_anthropic_kwargs(req, default_model=default_model)

        def _call() -> RathLLMChatResponse:
            message = self._client.messages.create(**kwargs)
            payload = message.model_dump(mode="json")
            return normalize_anthropic_response(payload)

        return retry_with_backoff(
            _call,
            max_attempts=self._provider.retry_max_attempts,
            base_seconds=self._provider.retry_base_seconds,
            extra_retryable=_ANTHROPIC_RETRYABLE,
        )
