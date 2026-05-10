"""Tests for :mod:`rath.flow.tool` functional factories."""

from __future__ import annotations

import pytest

import rath.backend as rb
import rath.flow.tool as ft
from rath.backend.tool_types import (
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)


def test_flow_tool_factories_match_constructors() -> None:
    assert ft.flow_tool_command_run("ls") == BackendToolCommandRun(cmd="ls")
    assert ft.flow_tool_command_run(
        "x", env={"A": "1"}, cwd="/", stdin=b"in", timeout=1.0
    ) == BackendToolCommandRun(
        cmd="x", env={"A": "1"}, cwd="/", stdin=b"in", timeout=1.0
    )
    assert ft.flow_tool_files_read("/p") == BackendToolFilesRead(path="/p")
    assert ft.flow_tool_files_read("/p", encoding=None) == BackendToolFilesRead(
        path="/p", encoding=None
    )
    assert ft.flow_tool_files_write("/p", b"hi") == BackendToolFilesWrite(
        path="/p", data=b"hi"
    )
    assert ft.flow_tool_files_write("/p", "t", mode=0o600) == (
        BackendToolFilesWrite(path="/p", data="t", mode=0o600)
    )
    assert ft.flow_tool_files_list("/d") == BackendToolFilesList(path="/d")
    assert ft.flow_tool_files_exists("/e") == BackendToolFilesExists(path="/e")
    assert ft.flow_tool_code_run("1+1") == BackendToolCodeRun(code="1+1")
    assert ft.flow_tool_code_run("x", language="python", timeout=3.0) == (
        BackendToolCodeRun(code="x", language="python", timeout=3.0)
    )


def test_flow_toolcall_is_distinct_abc_not_backend_marker() -> None:
    assert ft.FlowToolCall is not rb.BackendTool
    assert issubclass(ft.RunShellCommandTool, ft.FlowToolCall)


@pytest.mark.parametrize(
    "name",
    [
        "BackendTool",
        "BackendToolCommandRun",
        "flow_tool_command_run",
        "flow_tool_files_read",
    ],
)
def test_rath_flow_package_has_no_extra_exports(name: str) -> None:
    import rath.flow

    assert not hasattr(rath.flow, name)