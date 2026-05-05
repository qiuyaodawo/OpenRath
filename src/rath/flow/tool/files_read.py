"""Read file tool call."""

from __future__ import annotations

from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolFilesRead"]


@dataclass(frozen=True, slots=True)
class FlowToolFilesRead(FlowToolCall):
    """Read a file from the sandbox.

    With ``encoding`` set (default ``"utf-8"``) the result is text; pass
    ``encoding=None`` to read raw bytes.
    """

    path: str
    encoding: str | None = "utf-8"
