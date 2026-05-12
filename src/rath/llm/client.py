"""Synchronous OpenAI-compatible chat client (thin SDK wrapper)."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse
from rath.llm.provider import Provider

__all__ = ["RathOpenAIChatClient"]


class RathOpenAIChatClient:
    """Thin client around ``openai.OpenAI`` chat completions (non-streaming)."""

    def __init__(self, provider: Provider) -> None:
        key = (provider.api_key or "").strip()
        if not key:
            raise ValueError(
                "Provider.api_key is required to construct RathOpenAIChatClient",
            )
        self._provider = provider
        init_kw: dict[str, Any] = {"api_key": key}
        bu = (provider.base_url or "").strip()
        if bu:
            init_kw["base_url"] = bu
        self._client = OpenAI(**init_kw)

    @property
    def provider(self) -> Provider:
        return self._provider

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run ``chat.completions.create`` and normalize the response."""
        kwargs = to_create_kwargs(req, default_model=self._provider.model)
        completion = self._client.chat.completions.create(**kwargs)
        return normalize_chat_completion(completion)
