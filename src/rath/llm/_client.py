"""Synchronous OpenAI-compatible chat client (thin SDK wrapper)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openai import OpenAI

from rath.llm._openai_create_kwargs import to_create_kwargs
from rath.llm._openai_normalize import normalize_chat_completion
from rath.llm._settings import RathLLMSettings, load_rath_llm_settings
from rath.llm._types_request import RathLLMChatRequest
from rath.llm._types_response import RathLLMChatResponse

__all__ = ["RathOpenAIChatClient"]


class RathOpenAIChatClient:
    """Thin client around ``openai.OpenAI`` chat completions (non-streaming)."""

    def __init__(
        self,
        settings: RathLLMSettings | None = None,
        *,
        dotenv_path: Path | None = None,
    ) -> None:
        self._settings = (
            settings if settings is not None else load_rath_llm_settings(dotenv_path)
        )
        init_kw: dict[str, Any] = {"api_key": self._settings.api_key}
        if self._settings.base_url:
            init_kw["base_url"] = self._settings.base_url
        self._client = OpenAI(**init_kw)

    @property
    def settings(self) -> RathLLMSettings:
        return self._settings

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run ``chat.completions.create`` and normalize the response."""
        kwargs = to_create_kwargs(req, default_model=self._settings.default_model)
        completion = self._client.chat.completions.create(**kwargs)
        return normalize_chat_completion(completion)
