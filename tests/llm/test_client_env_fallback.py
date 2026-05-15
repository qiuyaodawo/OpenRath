"""Construction-only tests for env-variable fallbacks in RathOpenAIChatClient.

No network: ``openai.OpenAI(api_key=...)`` builds lazily, so we can assert how
``RathOpenAIChatClient`` resolves api_key/base_url across env vars without
hitting any remote endpoint.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from openai import AzureOpenAI, OpenAI

from rath.llm import Provider, RathOpenAIChatClient


@pytest.fixture(autouse=True)
def _clear_llm_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_KEY",
        "OPENAI_API_VERSION",
        "AZURE_OPENAI_API_VERSION",
    ):
        monkeypatch.delenv(name, raising=False)
    # Pin OPENRATH_HOME to an empty tmp dir so the config-file fallback tier
    # is inert for every test in this module; tests that want to exercise
    # config-driven behavior can write into that dir explicitly.
    isolated = tmp_path_factory.mktemp("openrath_home")
    monkeypatch.setenv("OPENRATH_HOME", str(isolated))
    yield


def test_provider_api_key_takes_precedence_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    client = RathOpenAIChatClient(Provider(api_key="from-provider"))
    assert isinstance(client._client, OpenAI)
    assert client._client.api_key == "from-provider"


def test_openai_api_key_env_fallback_when_provider_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    client = RathOpenAIChatClient(Provider())
    assert isinstance(client._client, OpenAI)
    assert client._client.api_key == "env-key"


def test_missing_everywhere_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # All env vars cleared and OPENRATH_HOME pinned to an empty dir by the
    # autouse fixture — no source supplies an api_key.
    with pytest.raises(ValueError, match="No API key found"):
        RathOpenAIChatClient(Provider())


def test_azure_v1_endpoint_uses_vanilla_openai_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Azure's ``/openai/v1`` surface is OpenAI-compatible — vanilla SDK."""
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.cognitiveservices.azure.com/openai/v1",
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-v1-key")
    client = RathOpenAIChatClient(Provider())
    assert isinstance(client._client, OpenAI)
    assert not isinstance(client._client, AzureOpenAI)
    assert client._client.api_key == "azure-v1-key"
    assert "cognitiveservices.azure.com/openai/v1" in str(client._client.base_url)


def test_azure_legacy_endpoint_uses_azure_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy ``/openai`` (no ``/v1``) routes through ``AzureOpenAI``."""
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.openai.azure.com/openai",
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-legacy-key")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01")
    client = RathOpenAIChatClient(Provider())
    assert isinstance(client._client, AzureOpenAI)
    assert client._client.api_key == "azure-legacy-key"
    # AzureOpenAI exposes api_version on the client
    assert client._client._api_version == "2024-12-01"


def test_azure_endpoint_prefers_azure_env_keys_over_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When base_url is Azure, AZURE_OPENAI_API_KEY beats OPENAI_API_KEY."""
    monkeypatch.setenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://example.cognitiveservices.azure.com/openai/v1",
    )
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-wins")
    monkeypatch.setenv("OPENAI_API_KEY", "should-be-ignored")
    client = RathOpenAIChatClient(Provider())
    assert client._client.api_key == "azure-wins"


def test_non_azure_endpoint_prefers_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """For a non-Azure base_url, OPENAI_API_KEY wins (Azure vars are a fallback)."""
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-should-lose")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-wins")
    client = RathOpenAIChatClient(Provider())
    assert client._client.api_key == "openai-wins"
