"""Tests for :mod:`rath.flow.tool` session helpers."""

from __future__ import annotations

import sys

import pytest

import rath.backend as rb
import rath.flow.tool as ft
from rath.backend import CodeResult, get
from rath.session import Session


def test_flow_tool_session_helpers_dispatch_local() -> None:
    """Each ``flow_tool_*`` helper dispatches through a local sandbox."""
    backend = get("local")
    with backend.open() as sb:
        sess = Session.from_user_message(".").bind_sandbox(sb)

        if sys.platform == "win32":
            r_cmd = ft.flow_tool_command_run(sess, "cmd /c echo flow_tool_cmd")
        else:
            r_cmd = ft.flow_tool_command_run(sess, ["sh", "-c", "echo flow_tool_cmd"])
        assert isinstance(r_cmd, rb.CommandResult)
        assert r_cmd.exit_code == 0
        assert b"flow_tool_cmd" in r_cmd.stdout.replace(b"\r\n", b"\n")

        wr = ft.flow_tool_files_write(sess, "_rath_unit_probe.txt", "Z", mode=0o600)
        assert isinstance(wr, rb.FileWriteResult)
        assert wr.bytes_written == 1

        rd = ft.flow_tool_files_read(sess, "_rath_unit_probe.txt")
        assert isinstance(rd, rb.FileContent)
        assert "Z" in str(rd.data)

        rd_bin = ft.flow_tool_files_read(sess, "_rath_unit_probe.txt", encoding=None)
        assert isinstance(rd_bin.data, bytes)

        ex = ft.flow_tool_files_exists(sess, "_rath_unit_probe.txt")
        assert ex is True

        ls = ft.flow_tool_files_list(sess, ".")
        assert isinstance(ls, rb.FileEntries)

        cr = ft.flow_tool_code_run(sess, "print(40+2)")
        assert isinstance(cr, CodeResult)
        assert b"42" in cr.stdout.replace(b"\r\n", b"\n")


def test_flow_toolcall_is_distinct_abc_not_backend_marker() -> None:
    """``FlowToolCall`` is a separate abstraction from ``BackendTool``."""
    assert ft.FlowToolCall is not rb.BackendTool
    assert issubclass(ft.FlowToolCommandRun, ft.FlowToolCall)


def test_flow_tool_does_not_reexport_backend_tool_types() -> None:
    """Backend payloads stay on ``rath.backend``; not re-exported here."""
    for name in (
        "BackendTool",
        "BackendToolCommandRun",
        "BackendToolFilesRead",
    ):
        assert not hasattr(ft, name)


@pytest.mark.parametrize(
    "name",
    [
        "flow_tool_command_run",
        "flow_tool_files_read",
        "FlowToolCommandRun",
    ],
)
def test_rath_flow_package_has_no_extra_exports(name: str) -> None:
    import rath.flow

    assert not hasattr(rath.flow, name)


def test_global_system_tools_registers_all_builtin_flow_tools() -> None:
    """All six built-in sandbox tools are registered by name."""
    keys = set(ft.global_system_tools().keys())
    assert keys == {
        "run_shell_command",
        "read_workspace_file",
        "write_workspace_file",
        "list_workspace_files",
        "workspace_path_exists",
        "run_code",
    }
