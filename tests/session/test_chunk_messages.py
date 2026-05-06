"""Unit tests for chunk rows and ``chunk_table_to_messages``."""

from __future__ import annotations

import json

from rath.llm import (
    RathLLMMessage,
    RathLLMToolCallFunction,
    RathLLMToolCallPart,
)
from rath.session.chunk import (
    ChunkKind,
    ChunkTable,
    assistant_turn_chunk,
    chunk_table_to_messages,
    system_text_chunk,
    tool_feedback_chunk,
    user_text_chunk,
)


def test_chunk_table_to_messages_order_and_roles() -> None:
    tab = ChunkTable(
        rows=(
            system_text_chunk("system body"),
            user_text_chunk("user body"),
        ),
    )
    msgs = chunk_table_to_messages(tab)
    assert len(msgs) == 2
    assert msgs[0] == RathLLMMessage(role="system", content="system body")
    assert msgs[1] == RathLLMMessage(role="user", content="user body")


def test_assistant_tool_calls_roundtrip_through_messages() -> None:
    part = RathLLMToolCallPart(
        id="tc1",
        type="function",
        function=RathLLMToolCallFunction(
            name="write_workspace_file",
            arguments=json.dumps({"path": "a.txt", "content": "z"}),
            arguments_parsed={"path": "a.txt", "content": "z"},
            arguments_parse_error=False,
        ),
    )
    row = assistant_turn_chunk(tool_calls=(part,), content="thinking")
    tab = ChunkTable(rows=(row,))
    msgs = chunk_table_to_messages(tab)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.role == "assistant"
    assert m.content == "thinking"
    assert m.tool_calls is not None
    assert len(m.tool_calls) == 1
    assert m.tool_calls[0]["id"] == "tc1"


def test_tool_feedback_row_maps_to_tool_message() -> None:
    tab = ChunkTable(
        rows=(
            tool_feedback_chunk("tc1", "write_workspace_file", '{"bytes_written": 3}'),
        ),
    )
    msgs = chunk_table_to_messages(tab)
    assert msgs[0].role == "tool"
    assert msgs[0].tool_call_id == "tc1"
    assert "bytes_written" in (msgs[0].content or "")


def test_chunk_kinds_distinct() -> None:
    assert ChunkKind.SYSTEM.value == "system"
