"""Concrete :class:`~rath.backend.tool_types.BackendTool` payload types."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "BackendTool",
    "BackendToolCommandRun",
    "BackendToolFilesRead",
    "BackendToolFilesWrite",
    "BackendToolFilesList",
    "BackendToolFilesExists",
    "BackendToolCodeRun",
]


class BackendTool:
    """Marker root for tool payloads passed to :meth:`~rath.backend.Backend.dispatch`."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class BackendToolCommandRun(BackendTool):
    """Run a shell command inside the sandbox."""

    cmd: str | Sequence[str]
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    stdin: bytes | None = None
    timeout: float | None = None


@dataclass(frozen=True, slots=True)
class BackendToolFilesRead(BackendTool):
    """Read a file from the sandbox."""

    path: str
    encoding: str | None = "utf-8"


@dataclass(frozen=True, slots=True)
class BackendToolFilesWrite(BackendTool):
    """Write a file inside the sandbox with the given Unix mode."""

    path: str
    data: bytes | str
    mode: int = 0o644


@dataclass(frozen=True, slots=True)
class BackendToolFilesList(BackendTool):
    """List entries (non-recursive) under a sandbox directory."""

    path: str


@dataclass(frozen=True, slots=True)
class BackendToolFilesExists(BackendTool):
    """Check whether a path exists inside the sandbox."""

    path: str


@dataclass(frozen=True, slots=True)
class BackendToolCodeRun(BackendTool):
    """Execute a code snippet inside the sandbox in the given language."""

    code: str
    language: str = "python"
    timeout: float | None = None
