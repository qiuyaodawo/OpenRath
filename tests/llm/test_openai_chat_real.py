"""Integration tests against a live OpenAI-compatible endpoint (no mocks)."""

from __future__ import annotations

import os

import pytest

from rath.llm import (
    RathLLMChatRequest,
    RathLLMFunctionTool,
    RathLLMMessage,
    RathOpenAIChatClient,
)
from tests.openai_env_provider import live_openai_provider

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        len(os.environ.get("OPENAI_API_KEY", "").strip()) < 8,
        reason="OPENAI_API_KEY not set or too short (live API tests)",
    ),
]


@pytest.fixture
def client() -> RathOpenAIChatClient:
    return RathOpenAIChatClient(live_openai_provider())


def test_openai_api_key_set_for_live_tests() -> None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    assert len(key) >= 8, "OPENAI_API_KEY must be exported for live LLM tests"


def test_rath_openai_chat_client_uses_explicit_provider(
    client: RathOpenAIChatClient,
) -> None:
    assert client.provider.api_key == os.environ["OPENAI_API_KEY"].strip()


def test_complete_ping_hits_remote_model(client: RathOpenAIChatClient) -> None:
    req = RathLLMChatRequest(
        messages=(
            RathLLMMessage(
                role="user",
                content="Reply with exactly the single word: pong",
            ),
        ),
        model=client.provider.model,
    )
    resp = client.complete(req)
    assert resp.id, "remote completions must return an id"
    assert resp.model
    assert len(resp.choices) >= 1
    text = (resp.primary_choice.message.content or "").strip().lower()
    assert "pong" in text
    assert resp.usage is not None
    assert resp.usage.total_tokens > 0
    assert resp.raw is not None
    assert resp.raw.get("object") == "chat.completion"


def test_complete_uses_provider_default_model_when_omitted(
    client: RathOpenAIChatClient,
) -> None:
    assert client.provider.model, (
        "OPENAI_DEFAULT_MODEL should be set for this test (or Provider.model)"
    )
    req = RathLLMChatRequest(
        messages=(RathLLMMessage(role="user", content="Say ok."),),
        model=None,
    )
    resp = client.complete(req)
    assert resp.model == client.provider.model


def test_function_tool_call_returns_add_arguments(client: RathOpenAIChatClient) -> None:
    tools = (
        RathLLMFunctionTool(
            name="add",
            description="Return the sum of two integers.",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "First summand"},
                    "b": {"type": "integer", "description": "Second summand"},
                },
                "required": ["a", "b"],
            },
        ),
    )
    req = RathLLMChatRequest(
        messages=(
            RathLLMMessage(
                role="user",
                content=(
                    "Call the add tool with a=40 and b=2 only. "
                    "Do not answer with plain text for the sum."
                ),
            ),
        ),
        model=client.provider.model,
        tools=tools,
        tool_choice="auto",
    )
    resp = client.complete(req)
    choice = resp.primary_choice
    assert choice.finish_reason in ("tool_calls", "stop")
    tc_list = choice.message.tool_calls
    assert tc_list is not None and len(tc_list) >= 1
    add_call = next((t for t in tc_list if t.function.name == "add"), None)
    assert add_call is not None
    assert add_call.function.arguments
    assert add_call.function.arguments_parse_error is False
    assert add_call.function.arguments_parsed is not None
    assert add_call.function.arguments_parsed.get("a") in (40, 40.0)
    assert add_call.function.arguments_parsed.get("b") in (2, 2.0)
