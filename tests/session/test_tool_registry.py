"""Tests for :func:`~rath.flow.tool.merge_tools_for_loop` and system tools."""

from __future__ import annotations

import pytest

from rath.backend import CommandResult, FileWriteResult, get
from rath.flow.tool import (
    FlowToolCall,
    FlowToolCommandRun,
    FlowToolFilesWrite,
    ToolNameConflictError,
    global_system_tools,
    merge_tools_for_loop,
    tools_dict_to_schemas,
)
from rath.session.session import Session


class _UserDummyTool(FlowToolCall):
    """Fixed name for merge / identity tests."""

    @property
    def name(self) -> str:
        return "user_dummy_xyz"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    def __call__(self, session: Session, arguments: dict[str, object]) -> int:
        return 1


def test_global_system_tools_has_expected_builtin_names() -> None:
    """Built-in registry exposes all six sandbox-facing LLM tools."""
    keys = set(global_system_tools().keys())
    assert keys == {
        "run_shell_command",
        "read_workspace_file",
        "write_workspace_file",
        "list_workspace_files",
        "workspace_path_exists",
        "run_code",
    }


def test_merge_tools_user_instance_identity() -> None:
    u = _UserDummyTool()
    table = merge_tools_for_loop([u])
    assert table["user_dummy_xyz"] is u
    assert table["run_shell_command"] is global_system_tools()["run_shell_command"]


def test_merge_tools_builtin_name_conflict_raises() -> None:
    """User tools cannot shadow a built-in tool name."""

    class _Shadow(FlowToolCall):
        @property
        def name(self) -> str:
            return "run_shell_command"

        @property
        def parameters(self) -> dict[str, object]:
            return {"type": "object", "properties": {}}

        def __call__(self, session: Session, arguments: dict[str, object]) -> int:
            return 0

    with pytest.raises(ToolNameConflictError, match="run_shell_command"):
        merge_tools_for_loop([_Shadow()])


def test_tools_dict_to_schemas_sorted_by_name() -> None:
    u = _UserDummyTool()
    table = merge_tools_for_loop([u])
    specs = tools_dict_to_schemas(table)
    assert [s.name for s in specs] == sorted(table.keys())


def test_flow_tool_command_run_dispatch_local_exit_code_and_stdout() -> None:
    backend = get("local")
    with backend.open() as sb:
        user = Session.from_user_message(".").bind_sandbox(sb)
        tool = FlowToolCommandRun()
        if __import__("sys").platform == "win32":
            cmd = "cmd /c echo 42"
        else:
            cmd = 'python -c "print(42)"'
        raw = tool(user, {"cmd": cmd})
    assert isinstance(raw, CommandResult)
    assert raw.exit_code == 0
    assert b"42" in raw.stdout.replace(b"\r\n", b"\n")


def test_flow_tool_files_write_returns_file_write_result() -> None:
    wt = FlowToolFilesWrite()
    backend = get("local")
    with backend.open() as sb:
        sess = Session.from_user_message(".").bind_sandbox(sb)
        raw = wt(sess, {"path": "_rath_reg_probe.txt", "content": "Z"})
    assert isinstance(raw, FileWriteResult)
    assert raw.bytes_written == 1
