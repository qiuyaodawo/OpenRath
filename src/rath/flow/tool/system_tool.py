"""Built-in sandbox-facing tools and ``flow_tool_*`` factories (→ :class:`~rath.backend.tool_types.BackendTool`)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from threading import Lock

from rath.backend.tool_types import (
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)
from rath.flow.tool.base import FlowToolCall
from rath.session.session import Session

__all__ = [
    "RunShellCommandTool",
    "WriteWorkspaceFileTool",
    "flow_tool_code_run",
    "flow_tool_command_run",
    "flow_tool_files_exists",
    "flow_tool_files_list",
    "flow_tool_files_read",
    "flow_tool_files_write",
    "global_system_tools",
]

# --- Factories (direct BackendTool constructors, for tests / manual dispatch) ---


def flow_tool_command_run(
    cmd: str | Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    stdin: bytes | None = None,
    timeout: float | None = None,
) -> BackendToolCommandRun:
    return BackendToolCommandRun(
        cmd=cmd, env=env, cwd=cwd, stdin=stdin, timeout=timeout
    )


def flow_tool_files_read(
    path: str, *, encoding: str | None = "utf-8"
) -> BackendToolFilesRead:
    return BackendToolFilesRead(path=path, encoding=encoding)


def flow_tool_files_write(
    path: str, data: bytes | str, *, mode: int = 0o644
) -> BackendToolFilesWrite:
    return BackendToolFilesWrite(path=path, data=data, mode=mode)


def flow_tool_files_list(path: str) -> BackendToolFilesList:
    return BackendToolFilesList(path=path)


def flow_tool_files_exists(path: str) -> BackendToolFilesExists:
    return BackendToolFilesExists(path=path)


def flow_tool_code_run(
    code: str,
    *,
    language: str = "python",
    timeout: float | None = None,
) -> BackendToolCodeRun:
    return BackendToolCodeRun(code=code, language=language, timeout=timeout)


# --- Built-in FlowToolCall wrappers for the session loop ---


class RunShellCommandTool(FlowToolCall):
    @property
    def name(self) -> str:
        return "run_shell_command"

    @property
    def description(self) -> str | None:
        return (
            "Run one shell command inside the active sandbox workspace. "
            "Prefer short commands such as ``echo Hello``."
        )

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "Shell command string",
                },
            },
            "required": ["cmd"],
            "additionalProperties": False,
        }

    def __call__(self, session: Session, arguments: Mapping[str, Any]) -> Any:
        cmd = arguments["cmd"]
        if not isinstance(cmd, str):
            cmd = str(cmd)
        if "\n" in cmd or "\r" in cmd:
            raise ValueError("multiline commands are rejected")
        if len(cmd) > 2048:
            raise ValueError("command too long")
        call = flow_tool_command_run(cmd=cmd)
        return session.require_sandbox().dispatch(call)


class WriteWorkspaceFileTool(FlowToolCall):
    @property
    def name(self) -> str:
        return "write_workspace_file"

    @property
    def description(self) -> str | None:
        return "Write UTF-8 text to a path inside the sandbox workspace."

    @property
    def parameters(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        }

    def __call__(self, session: Session, arguments: Mapping[str, Any]) -> Any:
        path = str(arguments["path"])
        raw = arguments["content"]
        if isinstance(raw, str):
            call = flow_tool_files_write(path=path, data=raw)
            return session.require_sandbox().dispatch(call)
        raise TypeError("content must be text for write_workspace_file")


_SYSTEM: dict[str, FlowToolCall] | None = None
_SYSTEM_LOCK = Lock()


def global_system_tools() -> dict[str, FlowToolCall]:
    """Process-wide built-in tools (singleton instances per name)."""

    global _SYSTEM
    with _SYSTEM_LOCK:
        if _SYSTEM is None:
            shell = RunShellCommandTool()
            write = WriteWorkspaceFileTool()
            _SYSTEM = {shell.name: shell, write.name: write}
        return _SYSTEM
