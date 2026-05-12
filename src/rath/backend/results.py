"""Typed results returned from :meth:`~rath.backend.Backend.dispatch`.

:class:`~rath.backend.tool_types.BackendToolFilesExists` is the only payload whose
dispatch result is a plain ``bool`` (not a :class:`ToolResult` subclass).
"""

from __future__ import annotations

from dataclasses import dataclass


class ToolResult:
    """Marker base class for all tool results.

    Concrete subclasses are dataclasses. :class:`~rath.backend.tool_types.BackendToolFilesExists`
    is the one backend tool payload that returns a plain ``bool`` instead of a
    :class:`ToolResult` subclass.
    """

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class CommandResult(ToolResult):
    """Result of :class:`~rath.backend.tool_types.BackendToolCommandRun`."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class FileContent(ToolResult):
    """Result of :class:`~rath.backend.tool_types.BackendToolFilesRead`.

    ``data`` is ``str`` when the call was made with an ``encoding`` set, or
    ``bytes`` when ``encoding=None``.
    """

    data: bytes | str


@dataclass(frozen=True, slots=True)
class FileEntry:
    """A single entry inside :class:`FileEntries`."""

    name: str
    path: str
    is_dir: bool


@dataclass(frozen=True, slots=True)
class FileEntries(ToolResult):
    """Result of :class:`~rath.backend.tool_types.BackendToolFilesList`.

    Entries are sorted by ``name`` for stable ordering.
    """

    entries: tuple[FileEntry, ...]


@dataclass(frozen=True, slots=True)
class FileWriteResult(ToolResult):
    """Result of :class:`~rath.backend.tool_types.BackendToolFilesWrite`.

    Holds the number of bytes actually written so that callers can verify
    the write without re-reading the file.
    """

    bytes_written: int


@dataclass(frozen=True, slots=True)
class ToolExecutionFailure(ToolResult):
    """Structured failure from :meth:`~rath.backend.abc.Backend.dispatch`.

    Prefer returning this instead of raising when the tool invocation itself failed
    or is unsupported, so the session loop can surface text to the model.
    """

    kind: str
    message: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class CodeResult(ToolResult):
    """Result of :class:`~rath.backend.tool_types.BackendToolCodeRun`.

    ``text`` holds the value of the last expression when the underlying
    runtime supports value extraction (e.g. a real code interpreter). For
    backends that only execute the script as a subprocess, ``text`` is
    ``None``.
    """

    text: str | None
    stdout: bytes
    stderr: bytes
    error: str | None
