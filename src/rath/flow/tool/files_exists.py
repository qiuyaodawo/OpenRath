"""Path existence check tool call."""

from __future__ import annotations

from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolFilesExists"]


@dataclass(frozen=True, slots=True)
class FlowToolFilesExists(FlowToolCall):
    """Check whether a path exists inside the sandbox."""

    path: str
