"""Tests for :func:`~rath.flow.tool.merge_tools_for_loop` and system tools."""

from __future__ import annotations

import pytest

from rath.backend import CommandResult, get
from rath.flow.tool import (
    FlowToolCall,
    ToolNameConflictError,
    global_system_tools,
    merge_tools_for_loop,
    tools_dict_to_schemas,
)
from rath.flow.tool.system_tool import RunShellCommandTool, WriteWorkspaceFileTool
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
    keys = set(global_system_tools().keys())
    assert keys == {"run_shell_command", "write_workspace_file"}


def test_merge_tools_user_instance_identity() -> None:
    u = _UserDummyTool()
    table = merge_tools_for_loop([u])
    assert table["user_dummy_xyz"] is u
    assert table["run_shell_command"] is global_system_tools()["run_shell_command"]


def test_merge_tools_builtin_name_conflict_raises() -> None:
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
    assert [s.name for s in specs] == [
        "run_shell_command",
        "user_dummy_xyz",
        "write_workspace_file",
    ]


def test_run_shell_command_tool_dispatch_local_exit_code_and_stdout() -> None:
    backend = get("local")
    with backend.open() as sb:
        user = Session.from_user_message(".").bind_sandbox(sb)
        tool = RunShellCommandTool()
        if __import__("sys").platform == "win32":
            cmd = "cmd /c echo 42"
        else:
            cmd = 'python -c "print(42)"'
        raw = tool(user, {"cmd": cmd})
    assert isinstance(raw, CommandResult)
    assert raw.exit_code == 0
    assert b"42" in raw.stdout.replace(b"\r\n", b"\n")


def test_write_workspace_tool_returns_file_write_result() -> None:
    from rath.backend import FileWriteResult

    wt = WriteWorkspaceFileTool()
    backend = get("local")
    with backend.open() as sb:
        sess = Session.from_user_message(".").bind_sandbox(sb)
        raw = wt(sess, {"path": "_rath_reg_probe.txt", "content": "Z"})
    assert isinstance(raw, FileWriteResult)
    assert raw.bytes_written == 1
