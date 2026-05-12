"""Synchronous OpenAI-compatible chat client (thin SDK wrapper)."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse
from rath.llm.provider import Provider

__all__ = ["RathOpenAIChatClient"]


class RathOpenAIChatClient:
    """Thin client around ``openai.OpenAI`` chat completions (non-streaming).

    Empty ``Provider.api_key`` / ``Provider.base_url`` fall back to the
    ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` environment variables. The values
    are typically populated from the project ``.env`` file when ``rath`` is
    imported (see :mod:`rath.__init__`).
    """

    def __init__(self, provider: Provider) -> None:
        key = (provider.api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            raise ValueError(
                "OPENAI_API_KEY is not set and Provider.api_key is empty; "
                "either pass api_key= to Provider(...) or export "
                "OPENAI_API_KEY (e.g. via a project .env file).",
            )
        self._provider = provider
        init_kw: dict[str, Any] = {"api_key": key}
        bu = (
            provider.base_url or os.environ.get("OPENAI_BASE_URL") or ""
        ).strip()
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
