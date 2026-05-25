"""Direct tests for :func:`rath.llm.anthropic.stream_deltas.anthropic_event_to_deltas`."""

from __future__ import annotations

from typing import Any

from rath.llm.anthropic.stream_deltas import anthropic_event_to_deltas


def _event(payload: dict[str, Any]) -> Any:
    class _Fake:
        type = payload.get("type")

        def model_dump(self, mode: str = "json") -> dict[str, Any]:
            return payload

    return _Fake()


def test_text_delta_yields_content_delta() -> None:
    ev = _event(
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "Hello"},
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    assert out[0].content_delta == "Hello"


def test_empty_text_delta_yields_nothing() -> None:
    ev = _event(
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": ""},
        }
    )
    assert list(anthropic_event_to_deltas(ev)) == []


def test_tool_use_start_yields_tool_call_fields() -> None:
    ev = _event(
        {
            "type": "content_block_start",
            "index": 1,
            "content_block": {
                "type": "tool_use",
                "id": "toolu_01",
                "name": "search",
            },
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    d = out[0]
    assert d.tool_call_index == 1
    assert d.tool_call_id == "toolu_01"
    assert d.tool_call_name_delta == "search"


def test_input_json_delta_yields_args_fragment() -> None:
    ev = _event(
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"q":'},
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    assert out[0].tool_call_args_delta == '{"q":'
    assert out[0].tool_call_index == 0


def test_message_delta_stop_reason_maps_to_finish() -> None:
    ev = _event(
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    assert out[0].finish_reason == "stop"


def test_message_delta_tool_use_stop_maps_to_tool_calls_finish() -> None:
    ev = _event(
        {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use"},
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    assert out[0].finish_reason == "tool_calls"


def test_message_delta_usage_yields_token_counts() -> None:
    ev = _event(
        {
            "type": "message_delta",
            "delta": {
                "usage": {"input_tokens": 10, "output_tokens": 4},
            },
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 1
    assert out[0].usage is not None
    assert out[0].usage.prompt_tokens == 10
    assert out[0].usage.completion_tokens == 4
    assert out[0].usage.total_tokens == 14


def test_message_delta_empty_usage_yields_nothing() -> None:
    ev = _event(
        {
            "type": "message_delta",
            "delta": {"usage": {}},
        }
    )
    assert list(anthropic_event_to_deltas(ev)) == []


def test_stop_and_usage_in_same_message_delta_yield_two_deltas() -> None:
    ev = _event(
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 2},
            },
        }
    )
    out = list(anthropic_event_to_deltas(ev))
    assert len(out) == 2
    assert out[0].finish_reason == "stop"
    assert out[1].usage is not None
    assert out[1].usage.total_tokens == 3
