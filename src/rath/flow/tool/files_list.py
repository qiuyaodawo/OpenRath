"""List directory tool call."""

from __future__ import annotations

from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolFilesList"]


@dataclass(frozen=True, slots=True)
class FlowToolFilesList(FlowToolCall):
    """List entries (non-recursive) under a sandbox directory."""

    path: str
