"""Loop tool registry helpers: merge user tools with system defaults, OpenAI schemas."""

from __future__ import annotations

from collections.abc import Mapping

from rath.flow.tool.base import FlowToolCall
from rath.flow.tool.system_tool import global_system_tools
from rath.llm import RathLLMFunctionTool

__all__ = [
    "ToolNameConflictError",
    "merge_tools_for_loop",
    "tools_dict_to_schemas",
]


class ToolNameConflictError(ValueError):
    """Raised when a user tool name collides with a built-in system tool."""


def merge_tools_for_loop(
    user_tools: list[FlowToolCall] | None,
) -> dict[str, FlowToolCall]:
    """Merge user tools with :func:`~rath.flow.tool.global_system_tools`.

    Built-in names cannot be shadowed; duplicates raise
    :class:`ToolNameConflictError`.
    """
    table = dict(global_system_tools())
    for t in user_tools or ():
        if t.name in table:
            raise ToolNameConflictError(
                f"user tool {t.name!r} shadows a built-in system tool"
            )
        table[t.name] = t
    return table


def tools_dict_to_schemas(
    table: Mapping[str, FlowToolCall],
) -> tuple[RathLLMFunctionTool, ...]:
    """Convert a name-to-tool map into sorted OpenAI-style function specs."""
    return tuple(
        RathLLMFunctionTool(
            name=tool.name,
            description=tool.description,
            parameters=dict(tool.parameters),
        )
        for _, tool in sorted(table.items(), key=lambda kv: kv[0])
    )
