"""Tests for :class:`RathAnthropicChatClient` (constructor + retry wiring).

The retry test patches ``self._client.messages.create`` so no real network
call is made and no anthropic API key is required for the actual SDK call -
we only need ``ANTHROPIC_API_KEY`` to be set for the constructor's
not-empty check (we set it on the Provider directly).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from rath.llm import Provider, RathLLMChatRequest, RathLLMMessage

anthropic = pytest.importorskip("anthropic")
from rath.llm.anthropic_client import (  # noqa: E402  -- importorskip gated
    RathAnthropicChatClient,
)


def _request() -> RathLLMChatRequest:
    return RathLLMChatRequest(
        model="claude-opus-4-7",
        messages=(RathLLMMessage(role="user", content="hi"),),
    )


def _fake_anthropic_message(text: str = "hi back") -> Any:
    """Build a minimal object that quacks like ``anthropic.types.Message``.

    Only :meth:`model_dump` is consulted by ``RathAnthropicChatClient``, so we
    return a simple namespace with that method.
    """
    payload = {
        "id": "msg_test",
        "model": "claude-opus-4-7",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": text}],
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    m = MagicMock()
    m.model_dump.return_value = payload
    return m


def _fake_rate_limit() -> "anthropic.RateLimitError":
    resp = httpx.Response(429, request=httpx.Request("POST", "https://x"))
    return anthropic.RateLimitError(message="rate limited", response=resp, body=None)


def _fake_connection_error() -> "anthropic.APIConnectionError":
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://x"))


def test_constructor_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        RathAnthropicChatClient(Provider())


def test_constructor_falls_back_to_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    # Should not raise; Provider has no api_key so env wins.
    client = RathAnthropicChatClient(Provider(model="claude-opus-4-7"))
    assert client.provider.model == "claude-opus-4-7"


def test_constructor_honors_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    client = RathAnthropicChatClient(
        Provider(model="claude-opus-4-7", base_url="https://proxy.example/v1")
    )
    # The SDK stores base_url on the client; assert it round-tripped.
    # ``anthropic.Anthropic`` exposes ``base_url`` as a public attribute.
    assert str(client._client.base_url).startswith("https://proxy.example")


def test_retry_fires_on_anthropic_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic-side ``RateLimitError`` must be retried, not propagated.

    Real (very-short) sleeps are fine here: with ``retry_base_seconds=0.001``
    and 2 backoffs the cumulative wait is ~3ms incl. jitter.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    client = RathAnthropicChatClient(
        Provider(
            model="claude-opus-4-7",
            retry_max_attempts=3,
            retry_base_seconds=0.001,
        )
    )

    calls = {"n": 0}

    def _create(**_kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _fake_rate_limit()
        return _fake_anthropic_message()

    monkeypatch.setattr(client._client.messages, "create", _create)

    resp = client.complete(_request())
    assert calls["n"] == 3  # retried twice, succeeded on third attempt
    assert resp.primary_choice.message.content == "hi back"


def test_retry_gives_up_after_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    client = RathAnthropicChatClient(
        Provider(
            model="claude-opus-4-7",
            retry_max_attempts=2,
            retry_base_seconds=0.001,
        )
    )

    def _always_fails(**_kwargs: Any) -> Any:
        raise _fake_connection_error()

    monkeypatch.setattr(client._client.messages, "create", _always_fails)

    with pytest.raises(anthropic.APIConnectionError):
        client.complete(_request())


def test_non_retryable_anthropic_error_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400-class error (e.g. BadRequestError) is not transient - propagate."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    client = RathAnthropicChatClient(
        Provider(
            model="claude-opus-4-7",
            retry_max_attempts=3,
            retry_base_seconds=0.001,
        )
    )

    def _bad_request(**_kwargs: Any) -> Any:
        resp = httpx.Response(400, request=httpx.Request("POST", "https://x"))
        raise anthropic.BadRequestError(message="bad request", response=resp, body=None)

    monkeypatch.setattr(client._client.messages, "create", _bad_request)

    with pytest.raises(anthropic.BadRequestError):
        client.complete(_request())


def test_complete_uses_default_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``Provider.model`` is empty, ``ANTHROPIC_DEFAULT_MODEL`` is used."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    monkeypatch.setenv("ANTHROPIC_DEFAULT_MODEL", "claude-opus-4-7-default")
    client = RathAnthropicChatClient(Provider())

    captured: dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return _fake_anthropic_message()

    monkeypatch.setattr(client._client.messages, "create", _create)

    req = RathLLMChatRequest(
        model=None,
        messages=(RathLLMMessage(role="user", content="hi"),),
    )
    client.complete(req)
    assert captured["model"] == "claude-opus-4-7-default"


def test_env_anthropic_default_model_only_consulted_when_model_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``Provider.model`` beats the env-default fallback."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-from-env")
    monkeypatch.setenv("ANTHROPIC_DEFAULT_MODEL", "should-not-be-used")
    client = RathAnthropicChatClient(Provider(model="claude-opus-4-7"))

    captured: dict[str, Any] = {}

    def _create(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return _fake_anthropic_message()

    monkeypatch.setattr(client._client.messages, "create", _create)
    req = RathLLMChatRequest(
        model=None,
        messages=(RathLLMMessage(role="user", content="hi"),),
    )
    client.complete(req)
    assert captured["model"] == "claude-opus-4-7"
    # Cleanup sanity: env not mutated by helper.
    assert os.environ["ANTHROPIC_DEFAULT_MODEL"] == "should-not-be-used"
