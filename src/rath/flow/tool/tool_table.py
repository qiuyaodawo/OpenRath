"""Process-wide tool registry used by session loop tool dispatch.

:class:`ToolTable` holds OpenAI-compatible function schemas and builders that
produce :class:`~rath.flow.tool.base.FlowToolCall` values from parsed JSON
arguments. Workflows register agents; tools register **here**.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any

from rath.flow.tool.base import FlowToolCall
from rath.flow.tool.command_run import FlowToolCommandRun
from rath.llm import RathLLMFunctionTool


@dataclass(frozen=True, slots=True)
class _ToolSpec:
    name: str
    description: str | None
    parameters: Mapping[str, Any]
    builder: Callable[[Mapping[str, Any]], FlowToolCall]


class ToolTable:
    """Maps tool name → schema + :class:`FlowToolCall` builder."""

    __slots__ = ("_tools", "_lock")

    def __init__(self) -> None:
        self._tools: dict[str, _ToolSpec] = {}
        self._lock = Lock()

    def register(
        self,
        name: str,
        *,
        builder: Callable[[Mapping[str, Any]], FlowToolCall],
        description: str | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Register or replace one tool."""
        schema = dict(parameters or {"type": "object", "properties": {}})
        spec = _ToolSpec(
            name=name,
            description=description,
            parameters=schema,
            builder=builder,
        )
        with self._lock:
            self._tools[name] = spec

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)

    def schemas(self) -> tuple[RathLLMFunctionTool, ...]:
        with self._lock:
            specs = sorted(self._tools.values(), key=lambda s: s.name)
        return tuple(
            RathLLMFunctionTool(
                name=s.name,
                description=s.description,
                parameters=dict(s.parameters),
            )
            for s in specs
        )

    def build(self, name: str, arguments: Mapping[str, Any] | None) -> FlowToolCall:
        with self._lock:
            try:
                spec = self._tools[name]
            except KeyError as exc:
                raise KeyError(name) from exc
            builder = spec.builder
        merged: dict[str, Any] = dict(arguments or {})
        return builder(merged)


_GLOBAL = ToolTable()


def global_tool_table() -> ToolTable:
    """Singleton used by :func:`run_session_loop` unless a table is injected."""
    return _GLOBAL


def register_builtin_session_tools(table: ToolTable | None = None) -> ToolTable:
    """Register defaults for sandbox session loops (shell + workspace write)."""

    target = table if table is not None else _GLOBAL

    def _shell_cmd(args: Mapping[str, Any]) -> FlowToolCall:
        cmd = args["cmd"]
        if not isinstance(cmd, str):
            cmd = str(cmd)
        if "\n" in cmd or "\r" in cmd:
            raise ValueError("multiline commands are rejected")
        if len(cmd) > 2048:
            raise ValueError("command too long")
        return FlowToolCommandRun(cmd=cmd)

    target.register(
        "run_shell_command",
        builder=_shell_cmd,
        description=(
            "Run one shell command inside the active sandbox workspace. "
            "Prefer short commands such as ``echo Hello``."
        ),
        parameters={
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Shell command string"},
            },
            "required": ["cmd"],
            "additionalProperties": False,
        },
    )

    def _write_file(args: Mapping[str, Any]) -> FlowToolCall:
        from rath.flow.tool import FlowToolFilesWrite

        path = str(args["path"])
        raw = args["content"]
        if isinstance(raw, str):
            return FlowToolFilesWrite(path=path, data=raw)
        raise TypeError("content must be text for write_workspace_file")

    target.register(
        "write_workspace_file",
        builder=_write_file,
        description="Write UTF-8 text to a path inside the sandbox workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    )

    return target


__all__ = ["ToolTable", "global_tool_table", "register_builtin_session_tools"]
