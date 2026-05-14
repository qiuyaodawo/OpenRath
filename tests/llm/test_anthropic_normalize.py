"""Pure-function tests for Anthropic <-> OpenRath translation.

No network calls and no Anthropic SDK runtime objects - the request builder
and response normalizer both operate on plain dicts, so we can drive them
with fixtures.
"""

from __future__ import annotations

import json

import pytest

from rath.llm import (
    Provider,
    RathLLMChatRequest,
    RathLLMFunctionTool,
    RathLLMMessage,
    build_anthropic_kwargs,
    normalize_anthropic_response,
)


def _request(**overrides: object) -> RathLLMChatRequest:
    defaults: dict[str, object] = {
        "messages": (
            RathLLMMessage(role="user", content="hi"),
        ),
        "tools": None,
    }
    defaults.update(overrides)
    return RathLLMChatRequest(**defaults)  # type: ignore[arg-type]


def test_system_messages_are_collapsed_into_system_field() -> None:
    req = _request(
        messages=(
            RathLLMMessage(role="system", content="prompt one"),
            RathLLMMessage(role="system", content="prompt two"),
            RathLLMMessage(role="user", content="ask"),
        ),
    )
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    assert kwargs["system"] == "prompt one\n\nprompt two"
    assert kwargs["messages"] == [{"role": "user", "content": "ask"}]


def test_default_max_tokens_when_request_does_not_set_one() -> None:
    req = _request()
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    assert kwargs["max_tokens"] == 4096


def test_tool_messages_become_user_tool_result_blocks() -> None:
    req = _request(
        messages=(
            RathLLMMessage(role="user", content="ask"),
            RathLLMMessage(
                role="tool",
                tool_call_id="tc-1",
                content='{"ok": true}',
            ),
        ),
    )
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    tool_msg = kwargs["messages"][1]
    assert tool_msg["role"] == "user"
    assert tool_msg["content"] == [
        {
            "type": "tool_result",
            "tool_use_id": "tc-1",
            "content": '{"ok": true}',
        }
    ]


def test_openai_style_tools_translate_to_input_schema() -> None:
    tool = RathLLMFunctionTool(
        name="my_tool",
        description="desc",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
    )
    req = _request(tools=(tool,))
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    assert kwargs["tools"] == [
        {
            "name": "my_tool",
            "description": "desc",
            "input_schema": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
            },
        }
    ]


def test_tool_choice_mapping() -> None:
    req = _request(tool_choice="required")
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    assert kwargs["tool_choice"] == {"type": "any"}

    req2 = _request(tool_choice={"type": "function", "function": {"name": "f"}})
    kwargs2 = build_anthropic_kwargs(req2, default_model="claude-opus-4-7")
    assert kwargs2["tool_choice"] == {"type": "tool", "name": "f"}


def test_assistant_tool_calls_become_assistant_content_blocks() -> None:
    args = {"path": "/etc/hosts"}
    req = _request(
        messages=(
            RathLLMMessage(
                role="assistant",
                content="thinking",
                tool_calls=(
                    {
                        "id": "tc-1",
                        "type": "function",
                        "function": {"name": "read", "arguments": json.dumps(args)},
                    },
                ),
            ),
        ),
    )
    kwargs = build_anthropic_kwargs(req, default_model="claude-opus-4-7")
    assistant = kwargs["messages"][0]
    assert assistant["role"] == "assistant"
    types = [b["type"] for b in assistant["content"]]
    assert types == ["text", "tool_use"]
    tu = assistant["content"][1]
    assert tu["name"] == "read"
    assert tu["input"] == args


def test_model_must_come_from_request_or_default() -> None:
    req = _request()
    with pytest.raises(ValueError, match="model is required"):
        build_anthropic_kwargs(req, default_model=None)


def test_normalize_text_only_response() -> None:
    payload = {
        "id": "msg_abc",
        "model": "claude-opus-4-7",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "hello"}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }
    resp = normalize_anthropic_response(payload)
    assert resp.id == "msg_abc"
    assert resp.model == "claude-opus-4-7"
    assert resp.primary_choice.finish_reason == "stop"
    assert resp.primary_choice.message.content == "hello"
    assert resp.primary_choice.message.tool_calls is None
    assert resp.usage is not None
    assert resp.usage.total_tokens == 30


def test_normalize_tool_use_response_maps_to_tool_calls() -> None:
    payload = {
        "id": "msg_2",
        "model": "claude-opus-4-7",
        "stop_reason": "tool_use",
        "content": [
            {"type": "text", "text": "thinking"},
            {
                "type": "tool_use",
                "id": "tu_1",
                "name": "search",
                "input": {"q": "hello"},
            },
        ],
        "usage": {"input_tokens": 5, "output_tokens": 7},
    }
    resp = normalize_anthropic_response(payload)
    assert resp.primary_choice.finish_reason == "tool_calls"
    msg = resp.primary_choice.message
    assert msg.tool_calls is not None
    assert len(msg.tool_calls) == 1
    tc = msg.tool_calls[0]
    assert tc.function.name == "search"
    assert tc.function.arguments_parsed == {"q": "hello"}
    assert json.loads(tc.function.arguments) == {"q": "hello"}


def test_normalize_handles_missing_usage() -> None:
    payload = {
        "id": "msg_3",
        "model": "claude-opus-4-7",
        "stop_reason": "max_tokens",
        "content": [{"type": "text", "text": "cut off"}],
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }
    resp = normalize_anthropic_response(payload)
    assert resp.primary_choice.finish_reason == "length"
    assert resp.usage is None


def test_provider_kind_field_round_trips() -> None:
    """Provider.provider_kind enables anthropic without changing existing fields."""
    p = Provider(provider_kind="anthropic", model="claude-opus-4-7")
    assert p.provider_kind == "anthropic"
    assert p.model == "claude-opus-4-7"
    # No provider_kind defaults to None (= openai).
    assert Provider().provider_kind is None
