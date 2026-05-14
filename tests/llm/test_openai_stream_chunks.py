"""Direct tests for :func:`rath.llm.client._chunk_to_deltas`.

The streaming loop tests already exercise this function indirectly through
a scripted client, but exercising it on real-shape OpenAI chunk dicts gives
us coverage that the SDK->delta translation is correct without needing the
full session loop.
"""

from __future__ import annotations

from typing import Any

from rath.llm.client import _chunk_to_deltas


def _chunk(payload: dict[str, Any]) -> Any:
    """Build a fake SDK chunk: any object with ``model_dump`` works."""

    class _Fake:
        def model_dump(self, mode: str = "json") -> dict[str, Any]:
            return payload

    return _Fake()


def test_content_chunk_yields_one_content_delta() -> None:
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "Hello"},
                    "finish_reason": None,
                }
            ],
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 1
    assert out[0].content_delta == "Hello"


def test_empty_content_string_is_skipped() -> None:
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": None,
                }
            ],
        }
    )
    assert list(_chunk_to_deltas(chunk)) == []


def test_tool_call_delta_chunk() -> None:
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "tc-1",
                                "function": {
                                    "name": "search",
                                    "arguments": '{"q',
                                },
                            }
                        ],
                    },
                    "finish_reason": None,
                }
            ],
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 1
    d = out[0]
    assert d.tool_call_index == 0
    assert d.tool_call_id == "tc-1"
    assert d.tool_call_name_delta == "search"
    assert d.tool_call_args_delta == '{"q'


def test_finish_chunk_yields_finish_delta() -> None:
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 1
    assert out[0].finish_reason == "stop"


def test_unknown_finish_reason_is_dropped() -> None:
    """An unexpected finish_reason value coerces to None (not yielded)."""
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "weird_new_reason",
                }
            ],
        }
    )
    assert list(_chunk_to_deltas(chunk)) == []


def test_usage_only_final_chunk() -> None:
    chunk = _chunk(
        {
            "choices": [],
            "usage": {
                "prompt_tokens": 42,
                "completion_tokens": 7,
                "total_tokens": 49,
            },
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 1
    assert out[0].usage is not None
    assert out[0].usage.prompt_tokens == 42
    assert out[0].usage.completion_tokens == 7
    assert out[0].usage.total_tokens == 49


def test_usage_only_chunk_with_empty_usage_yields_nothing() -> None:
    chunk = _chunk({"choices": [], "usage": {}})
    assert list(_chunk_to_deltas(chunk)) == []


def test_multiple_choices_only_first_is_consulted() -> None:
    """OpenRath does not support n>1; extra choices are ignored."""
    chunk = _chunk(
        {
            "choices": [
                {"index": 0, "delta": {"content": "A"}, "finish_reason": None},
                {"index": 1, "delta": {"content": "B"}, "finish_reason": None},
            ],
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 1
    assert out[0].content_delta == "A"


def test_content_and_finish_in_same_chunk_yields_two_deltas() -> None:
    chunk = _chunk(
        {
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "bye"},
                    "finish_reason": "stop",
                }
            ],
        }
    )
    out = list(_chunk_to_deltas(chunk))
    assert len(out) == 2
    assert out[0].content_delta == "bye"
    assert out[1].finish_reason == "stop"
