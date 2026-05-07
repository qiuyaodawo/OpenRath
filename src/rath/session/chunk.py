"""Chunk rows for conversation content on each Session."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, cast

from rath.llm import RathLLMMessage, RathLLMToolCallPart


class ChunkKind(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"


@dataclass(frozen=True, slots=True)
class ChunkRow:
    """Immutable row in chronological order."""

    kind: ChunkKind
    payload: dict[str, Any]


def user_text_chunk(text: str) -> ChunkRow:
    """User message row for :attr:`ChunkKind.USER`."""
    return ChunkRow(kind=ChunkKind.USER, payload={"content": text})


def system_text_chunk(text: str) -> ChunkRow:
    """System prompt row for :attr:`ChunkKind.SYSTEM`."""
    return ChunkRow(kind=ChunkKind.SYSTEM, payload={"content": text})


def assistant_turn_chunk(
    *,
    tool_calls: tuple[RathLLMToolCallPart, ...] | None,
    content: str | None = None,
) -> ChunkRow:
    """Assistant message row; ``tool_calls`` are stored in OpenAI-style wire form."""
    wire: list[dict[str, Any]] | None = None
    if tool_calls:
        wire = []
        for p in tool_calls:
            wire.append(
                {
                    "id": p.id,
                    "type": p.type,
                    "function": {
                        "name": p.function.name,
                        "arguments": p.function.arguments,
                    },
                }
            )
    return ChunkRow(
        kind=ChunkKind.ASSISTANT,
        payload={"content": content, "tool_calls": wire},
    )


def tool_feedback_chunk(tool_call_id: str, name: str, body: str) -> ChunkRow:
    """Tool result chunk for replay into the chat transcript."""
    return ChunkRow(
        kind=ChunkKind.TOOL_RESULT,
        payload={"tool_call_id": tool_call_id, "name": name, "content": body},
    )


@dataclass(frozen=True, slots=True)
class ChunkTable:
    """Append-only chronological chunk list."""

    rows: tuple[ChunkRow, ...] = ()

    def extend(self, *additional: ChunkRow) -> ChunkTable:
        return ChunkTable(rows=self.rows + tuple(additional))


def chunk_table_to_messages(tab: ChunkTable) -> tuple[RathLLMMessage, ...]:
    """Flatten chunk history into Rath LLM wire messages."""

    msgs: list[RathLLMMessage] = []
    for row in tab.rows:
        k = row.kind
        p = row.payload
        if k == ChunkKind.SYSTEM:
            msgs.append(RathLLMMessage(role="system", content=str(p["content"])))
        elif k == ChunkKind.USER:
            msgs.append(RathLLMMessage(role="user", content=str(p["content"])))
        elif k == ChunkKind.ASSISTANT:
            content_val = p.get("content")
            content = None if content_val is None else str(content_val)
            tc_raw = p.get("tool_calls")
            tc_tuple: tuple[Mapping[str, Any], ...] | None = None
            if tc_raw:
                lst = [cast(Mapping[str, Any], dict(d)) for d in tc_raw]
                tc_tuple = tuple(lst)
            msgs.append(
                RathLLMMessage(
                    role="assistant",
                    content=content,
                    tool_calls=tc_tuple,
                )
            )
        elif k == ChunkKind.TOOL_RESULT:
            msgs.append(
                RathLLMMessage(
                    role="tool",
                    content=str(p["content"]),
                    tool_call_id=str(p["tool_call_id"]),
                )
            )
    return tuple(msgs)
