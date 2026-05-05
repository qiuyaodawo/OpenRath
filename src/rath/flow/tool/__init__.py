"""Functional factories for :class:`FlowToolCall` values (torch.nn.functional-style).

Use :func:`flow_tool_command_run` and siblings when you prefer call-site kwargs
over spelling the dataclass constructor; both produce the same immutable
objects that :meth:`~rath.backend.Backend.dispatch` consumes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rath.flow.tool._calls import (
    FlowToolCall,
    FlowToolCodeRun,
    FlowToolCommandRun,
    FlowToolFilesExists,
    FlowToolFilesList,
    FlowToolFilesRead,
    FlowToolFilesWrite,
)


def flow_tool_command_run(
    cmd: str | Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    stdin: bytes | None = None,
    timeout: float | None = None,
) -> FlowToolCommandRun:
    """Build :class:`FlowToolCommandRun`."""
    return FlowToolCommandRun(
        cmd=cmd, env=env, cwd=cwd, stdin=stdin, timeout=timeout
    )


def flow_tool_files_read(
    path: str, *, encoding: str | None = "utf-8"
) -> FlowToolFilesRead:
    """Build :class:`FlowToolFilesRead`."""
    return FlowToolFilesRead(path=path, encoding=encoding)


def flow_tool_files_write(
    path: str, data: bytes | str, *, mode: int = 0o644
) -> FlowToolFilesWrite:
    """Build :class:`FlowToolFilesWrite`."""
    return FlowToolFilesWrite(path=path, data=data, mode=mode)


def flow_tool_files_list(path: str) -> FlowToolFilesList:
    """Build :class:`FlowToolFilesList`."""
    return FlowToolFilesList(path=path)


def flow_tool_files_exists(path: str) -> FlowToolFilesExists:
    """Build :class:`FlowToolFilesExists`."""
    return FlowToolFilesExists(path=path)


def flow_tool_code_run(
    code: str, *, language: str = "python", timeout: float | None = None
) -> FlowToolCodeRun:
    """Build :class:`FlowToolCodeRun`."""
    return FlowToolCodeRun(code=code, language=language, timeout=timeout)


__all__ = [
    "FlowToolCall",
    "FlowToolCodeRun",
    "FlowToolCommandRun",
    "FlowToolFilesExists",
    "FlowToolFilesList",
    "FlowToolFilesRead",
    "FlowToolFilesWrite",
    "flow_tool_code_run",
    "flow_tool_command_run",
    "flow_tool_files_exists",
    "flow_tool_files_list",
    "flow_tool_files_read",
    "flow_tool_files_write",
]
