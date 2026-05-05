"""Code snippet execution tool call."""

from __future__ import annotations

from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolCodeRun"]


@dataclass(frozen=True, slots=True)
class FlowToolCodeRun(FlowToolCall):
    """Execute a code snippet inside the sandbox in the given language."""

    code: str
    language: str = "python"
    timeout: float | None = None
