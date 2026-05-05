"""Frozen value objects for tool calls dispatched by :class:`~rath.backend.Backend`.

Each :class:`FlowToolCall` subclass is the smallest unit of sandbox work. They
are immutable dataclasses with ``slots=True`` for value semantics comparable to
PyTorch ops in ``torch.fx`` graphs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class FlowToolCall:
    """Marker base for all flow tool call types.

    Concrete subclasses are dataclasses; this base lets
    :meth:`~rath.backend.Backend.supported_calls` return
    ``frozenset[type[FlowToolCall]]`` and keeps pattern matching on a single
    discriminator root.
    """

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class FlowToolCommandRun(FlowToolCall):
    """Run a shell command inside the sandbox."""

    cmd: str | Sequence[str]
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    stdin: bytes | None = None
    timeout: float | None = None


@dataclass(frozen=True, slots=True)
class FlowToolFilesRead(FlowToolCall):
    """Read a file from the sandbox.

    With ``encoding`` set (default ``"utf-8"``) the result is text; pass
    ``encoding=None`` to read raw bytes.
    """

    path: str
    encoding: str | None = "utf-8"


@dataclass(frozen=True, slots=True)
class FlowToolFilesWrite(FlowToolCall):
    """Write a file inside the sandbox with the given Unix mode."""

    path: str
    data: bytes | str
    mode: int = 0o644


@dataclass(frozen=True, slots=True)
class FlowToolFilesList(FlowToolCall):
    """List entries (non-recursive) under a sandbox directory."""

    path: str


@dataclass(frozen=True, slots=True)
class FlowToolFilesExists(FlowToolCall):
    """Check whether a path exists inside the sandbox."""

    path: str


@dataclass(frozen=True, slots=True)
class FlowToolCodeRun(FlowToolCall):
    """Execute a code snippet inside the sandbox in the given language."""

    code: str
    language: str = "python"
    timeout: float | None = None


__all__ = [
    "FlowToolCall",
    "FlowToolCodeRun",
    "FlowToolCommandRun",
    "FlowToolFilesExists",
    "FlowToolFilesList",
    "FlowToolFilesRead",
    "FlowToolFilesWrite",
]
