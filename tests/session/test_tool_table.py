"""Tests for :class:`~rath.flow.tool.tool_table.ToolTable` defaults."""

from __future__ import annotations

import pytest

from rath.flow.tool import FlowToolCommandRun, FlowToolFilesWrite
from rath.flow.tool.tool_table import ToolTable, register_builtin_session_tools


def test_register_builtin_includes_expected_tools() -> None:
    table = ToolTable()
    register_builtin_session_tools(table)
    names = {s.name for s in table.schemas()}
    assert "run_shell_command" in names
    assert "write_workspace_file" in names


def test_build_run_shell_command() -> None:
    table = ToolTable()
    register_builtin_session_tools(table)
    call = table.build("run_shell_command", {"cmd": "echo x"})
    assert isinstance(call, FlowToolCommandRun)
    assert call.cmd == "echo x"


def test_build_write_workspace_file() -> None:
    table = ToolTable()
    register_builtin_session_tools(table)
    call = table.build(
        "write_workspace_file",
        {"path": "rel.txt", "content": "body"},
    )
    assert isinstance(call, FlowToolFilesWrite)
    assert call.path == "rel.txt"
    assert call.data == "body"


def test_reject_multiline_shell_command() -> None:
    table = ToolTable()
    register_builtin_session_tools(table)
    with pytest.raises(ValueError, match="multiline"):
        table.build("run_shell_command", {"cmd": "echo\nbad"})


def test_reject_oversized_shell_command() -> None:
    table = ToolTable()
    register_builtin_session_tools(table)
    with pytest.raises(ValueError, match="too long"):
        table.build("run_shell_command", {"cmd": "x" * 3000})


def test_missing_tool_raises() -> None:
    table = ToolTable()
    with pytest.raises(KeyError):
        table.build("nonexistent", {})
