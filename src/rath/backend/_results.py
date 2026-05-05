"""Tool result value objects.

Mirrors the structure of :mod:`rath.flow.tool` call types: every concrete result
is a frozen, slotted dataclass. :class:`~rath.flow.tool.FlowToolFilesExists`
intentionally yields the bare ``bool`` from dispatch rather than a wrapper,
since wrapping a single boolean adds no information.
"""

from __future__ import annotations

from dataclasses import dataclass


class ToolResult:
    """Marker base class for all tool results.

    Concrete subclasses are dataclasses. :class:`~rath.flow.tool.FlowToolFilesExists`
    is the one flow tool call that returns a plain ``bool`` instead of a
    :class:`ToolResult` subclass.
    """

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class CommandResult(ToolResult):
    """Result of :class:`~rath.flow.tool.FlowToolCommandRun`."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class FileContent(ToolResult):
    """Result of :class:`~rath.flow.tool.FlowToolFilesRead`.

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
    """Result of :class:`~rath.flow.tool.FlowToolFilesList`.

    Entries are sorted by ``name`` so that conformance tests can compare
    output across backends.
    """

    entries: tuple[FileEntry, ...]


@dataclass(frozen=True, slots=True)
class FileWriteResult(ToolResult):
    """Result of :class:`~rath.flow.tool.FlowToolFilesWrite`.

    Holds the number of bytes actually written so that callers can verify
    the write without re-reading the file.
    """

    bytes_written: int


@dataclass(frozen=True, slots=True)
class CodeResult(ToolResult):
    """Result of :class:`~rath.flow.tool.FlowToolCodeRun`.

    ``text`` holds the value of the last expression when the underlying
    runtime supports value extraction (e.g. a real code interpreter). For
    backends that only execute the script as a subprocess, ``text`` is
    ``None``.
    """

    text: str | None
    stdout: bytes
    stderr: bytes
    error: str | None
