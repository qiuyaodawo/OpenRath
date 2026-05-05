"""Write file tool call."""

from __future__ import annotations

from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolFilesWrite"]


@dataclass(frozen=True, slots=True)
class FlowToolFilesWrite(FlowToolCall):
    """Write a file inside the sandbox with the given Unix mode."""

    path: str
    data: bytes | str
    mode: int = 0o644
