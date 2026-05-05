"""Shell command execution tool call."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rath.flow.tool.base import FlowToolCall

__all__ = ["FlowToolCommandRun"]


@dataclass(frozen=True, slots=True)
class FlowToolCommandRun(FlowToolCall):
    """Run a shell command inside the sandbox."""

    cmd: str | Sequence[str]
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    stdin: bytes | None = None
    timeout: float | None = None
