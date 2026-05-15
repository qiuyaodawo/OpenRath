"""Runtime checks for :class:`ChatClient` / :class:`StreamingChatClient` Protocol membership."""

from __future__ import annotations

from typing import Iterator

import pytest

from rath.llm import (
    ChatClient,
    Provider,
    RathAnthropicChatClient,
    RathOpenAIChatClient,
    StreamingChatClient,
)


@pytest.fixture(autouse=True)
def _stub_credentials(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")
    for v in (
        "OPENAI_BASE_URL",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_API_KEY",
    ):
        monkeypatch.delenv(v, raising=False)
    yield


def test_openai_client_is_chat_client() -> None:
    client = RathOpenAIChatClient(Provider())
    assert isinstance(client, ChatClient)


def test_openai_client_is_streaming() -> None:
    client = RathOpenAIChatClient(Provider())
    assert isinstance(client, StreamingChatClient)


def test_anthropic_client_is_chat_client() -> None:
    client = RathAnthropicChatClient(Provider(provider_kind="anthropic"))
    assert isinstance(client, ChatClient)


def test_anthropic_client_is_not_streaming() -> None:
    client = RathAnthropicChatClient(Provider(provider_kind="anthropic"))
    assert not isinstance(client, StreamingChatClient)
