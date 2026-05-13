"""Synchronous OpenAI-compatible chat client (thin SDK wrapper)."""

from __future__ import annotations

import os
from typing import Any

from openai import AzureOpenAI, OpenAI

from rath.llm.openai_create_kwargs import to_create_kwargs
from rath.llm.openai_normalize import normalize_chat_completion
from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse
from rath.llm.provider import Provider

__all__ = ["RathOpenAIChatClient"]


def _is_azure_endpoint(url: str) -> bool:
    return ".azure.com" in url or ".cognitiveservices.azure.com" in url


def _resolve_base_url(provider: Provider) -> str:
    """Pick the first non-empty source: provider, OPENAI_BASE_URL, AZURE_OPENAI_ENDPOINT."""
    for candidate in (
        provider.base_url,
        os.environ.get("OPENAI_BASE_URL"),
        os.environ.get("AZURE_OPENAI_ENDPOINT"),
    ):
        if candidate and candidate.strip():
            return candidate.strip()
    return ""


def _resolve_api_key(provider: Provider, base_url: str) -> str:
    """Pick the first non-empty source.

    For Azure endpoints, Azure-specific env vars are tried first; otherwise
    ``OPENAI_API_KEY`` wins. ``Provider.api_key`` always takes precedence.
    """
    sources: list[str | None] = [provider.api_key]
    if _is_azure_endpoint(base_url):
        sources += [
            os.environ.get("AZURE_OPENAI_API_KEY"),
            os.environ.get("AZURE_API_KEY"),
            os.environ.get("OPENAI_API_KEY"),
        ]
    else:
        sources += [
            os.environ.get("OPENAI_API_KEY"),
            os.environ.get("AZURE_OPENAI_API_KEY"),
        ]
    for candidate in sources:
        if candidate and candidate.strip():
            return candidate.strip()
    return ""


class RathOpenAIChatClient:
    """Thin client around ``openai.OpenAI`` chat completions (non-streaming).

    Empty ``Provider.api_key`` / ``Provider.base_url`` fall back to environment
    variables, typically loaded from the project ``.env`` (see
    :mod:`rath.__init__`):

    * ``base_url``: ``OPENAI_BASE_URL`` then ``AZURE_OPENAI_ENDPOINT``.
    * ``api_key``: ``OPENAI_API_KEY`` for OpenAI-compatible endpoints; for
      ``*.azure.com`` endpoints the order becomes
      ``AZURE_OPENAI_API_KEY`` → ``AZURE_API_KEY`` → ``OPENAI_API_KEY``.

    Azure endpoints exposing the new ``/openai/v1`` surface speak plain
    OpenAI Chat Completions, so the vanilla SDK is used. Legacy Azure
    endpoints (``/openai`` without ``/v1``) are routed through
    :class:`openai.AzureOpenAI` with ``api_version`` taken from
    ``OPENAI_API_VERSION`` (default ``2024-10-21``).
    """

    def __init__(self, provider: Provider) -> None:
        base_url = _resolve_base_url(provider)
        key = _resolve_api_key(provider, base_url)
        if not key:
            raise ValueError(
                "No API key found: Provider.api_key is empty and none of "
                "OPENAI_API_KEY / AZURE_OPENAI_API_KEY / AZURE_API_KEY are "
                "set. Pass api_key= to Provider(...) or export one of these "
                "(e.g. via a project .env file).",
            )
        self._provider = provider

        use_azure_legacy = (
            _is_azure_endpoint(base_url) and "/openai/v1" not in base_url
        )
        if use_azure_legacy:
            api_version = (
                os.environ.get("OPENAI_API_VERSION")
                or os.environ.get("AZURE_OPENAI_API_VERSION")
                or "2024-10-21"
            )
            self._client = AzureOpenAI(
                api_key=key,
                azure_endpoint=base_url,
                api_version=api_version,
            )
        else:
            init_kw: dict[str, Any] = {"api_key": key}
            if base_url:
                init_kw["base_url"] = base_url
            self._client = OpenAI(**init_kw)

    @property
    def provider(self) -> Provider:
        return self._provider

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        """Run ``chat.completions.create`` and normalize the response."""
        kwargs = to_create_kwargs(req, default_model=self._provider.model)
        completion = self._client.chat.completions.create(**kwargs)
        return normalize_chat_completion(completion)
