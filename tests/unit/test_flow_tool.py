"""Tests for :mod:`rath.flow.tool` functional factories."""

from __future__ import annotations

import pytest

import rath.backend as rb
import rath.flow.tool as ft


def test_flow_tool_factories_match_constructors() -> None:
    assert ft.flow_tool_command_run("ls") == ft.FlowToolCommandRun(cmd="ls")
    assert ft.flow_tool_command_run(
        "x", env={"A": "1"}, cwd="/", stdin=b"in", timeout=1.0
    ) == ft.FlowToolCommandRun(
        cmd="x", env={"A": "1"}, cwd="/", stdin=b"in", timeout=1.0
    )
    assert ft.flow_tool_files_read("/p") == ft.FlowToolFilesRead(path="/p")
    assert ft.flow_tool_files_read("/p", encoding=None) == ft.FlowToolFilesRead(
        path="/p", encoding=None
    )
    assert ft.flow_tool_files_write("/p", b"hi") == ft.FlowToolFilesWrite(
        path="/p", data=b"hi"
    )
    assert ft.flow_tool_files_write("/p", "t", mode=0o600) == (
        ft.FlowToolFilesWrite(path="/p", data="t", mode=0o600)
    )
    assert ft.flow_tool_files_list("/d") == ft.FlowToolFilesList(path="/d")
    assert ft.flow_tool_files_exists("/e") == ft.FlowToolFilesExists(path="/e")
    assert ft.flow_tool_code_run("1+1") == ft.FlowToolCodeRun(code="1+1")
    assert ft.flow_tool_code_run("x", language="python", timeout=3.0) == (
        ft.FlowToolCodeRun(code="x", language="python", timeout=3.0)
    )


def test_backend_reexports_are_identical_to_flow_tool() -> None:
    assert rb.FlowToolCommandRun is ft.FlowToolCommandRun
    assert rb.FlowToolCall is ft.FlowToolCall
    assert rb.FlowToolFilesRead is ft.FlowToolFilesRead


@pytest.mark.parametrize(
    "name",
    [
        "FlowToolCall",
        "FlowToolCommandRun",
        "flow_tool_command_run",
        "flow_tool_files_read",
    ],
)
def test_rath_flow_package_has_no_extra_exports(name: str) -> None:
    import rath.flow

    assert not hasattr(rath.flow, name)
