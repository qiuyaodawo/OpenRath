"""Synchronous OpenAI-compatible chat client (thin SDK wrapper)."""

from __future__ import annotations

import os
from typing import Any, Iterator

from openai import AzureOpenAI, OpenAI

from rath.llm._retry import retry_with_backoff
from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import (
    RathLLMChatResponse,
    RathLLMFinishReason,
    RathLLMStreamDelta,
    RathLLMTokenUsage,
)
from rath.llm.openai_create_kwargs import to_create_kwargs, to_create_kwargs_stream
from rath.llm.openai_normalize import normalize_chat_completion
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


_STREAM_FINISH_REASONS = frozenset(
    {"stop", "length", "tool_calls", "content_filter", "function_call"}
)


def _coerce_stream_finish(value: Any) -> RathLLMFinishReason | None:
    if isinstance(value, str) and value in _STREAM_FINISH_REASONS:
        return value  # type: ignore[return-value]
    return None


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
        self._client: OpenAI | AzureOpenAI

        use_azure_legacy = _is_azure_endpoint(base_url) and "/openai/v1" not in base_url
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
        """Run ``chat.completions.create`` and normalize the response.

        Transient errors (rate limit, connection, timeout, server 5xx) are
        retried with exponential backoff per :attr:`Provider.retry_max_attempts`
        and :attr:`Provider.retry_base_seconds`.
        """
        default_model = self._provider.model or os.environ.get("OPENAI_DEFAULT_MODEL")
        kwargs = to_create_kwargs(req, default_model=default_model)

        def _call() -> RathLLMChatResponse:
            completion = self._client.chat.completions.create(**kwargs)
            return normalize_chat_completion(completion)

        return retry_with_backoff(
            _call,
            max_attempts=self._provider.retry_max_attempts,
            base_seconds=self._provider.retry_base_seconds,
        )

    def complete_stream(self, req: RathLLMChatRequest) -> Iterator[RathLLMStreamDelta]:
        """Yield ``RathLLMStreamDelta`` for each chunk of a streaming completion.

        Transient errors during the initial ``create`` call are retried; once
        the iterator starts producing chunks, retries are no longer possible
        (the stream is committed).
        """
        default_model = self._provider.model or os.environ.get("OPENAI_DEFAULT_MODEL")
        kwargs = to_create_kwargs_stream(req, default_model=default_model)

        def _open_stream() -> Any:
            return self._client.chat.completions.create(**kwargs)

        stream = retry_with_backoff(
            _open_stream,
            max_attempts=self._provider.retry_max_attempts,
            base_seconds=self._provider.retry_base_seconds,
        )
        for chunk in stream:
            yield from _chunk_to_deltas(chunk)


def _chunk_to_deltas(chunk: Any) -> Iterator[RathLLMStreamDelta]:
    """Map one OpenAI stream chunk to one or more :class:`RathLLMStreamDelta`.

    OpenRath does not support ``n>1`` completions (the chat request shape
    only carries a single choice downstream), so only ``choices[0]`` is
    inspected here; additional choices in the chunk are silently dropped.
    """
    payload = (
        chunk.model_dump(mode="json") if hasattr(chunk, "model_dump") else dict(chunk)
    )
    choices = payload.get("choices") or []
    if not choices:
        # Final usage-only chunk (when stream_options['include_usage'] is set).
        usage = payload.get("usage") or {}
        if isinstance(usage, dict) and (
            usage.get("prompt_tokens") or usage.get("completion_tokens")
        ):
            yield RathLLMStreamDelta(
                usage=RathLLMTokenUsage(
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                ),
            )
        return

    choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = choice.get("delta") or {}
    finish = _coerce_stream_finish(choice.get("finish_reason"))
    content_delta = delta.get("content")
    if isinstance(content_delta, str) and content_delta:
        yield RathLLMStreamDelta(content_delta=content_delta)

    tcalls = delta.get("tool_calls") or []
    for tc in tcalls:
        if not isinstance(tc, dict):
            continue
        idx = tc.get("index")
        fn = tc.get("function") or {}
        yield RathLLMStreamDelta(
            tool_call_index=int(idx) if isinstance(idx, int) else None,
            tool_call_id=tc.get("id"),
            tool_call_name_delta=fn.get("name"),
            tool_call_args_delta=fn.get("arguments"),
        )

    if finish is not None:
        yield RathLLMStreamDelta(finish_reason=finish)
