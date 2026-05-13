"""Tool registration, :class:`~rath.flow.tool.base.FlowToolCall`, and session-scoped helpers."""

from __future__ import annotations

from rath.backend.tool_types import (
    BackendTool,
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
)
from rath.flow.tool.base import FlowToolCall
from rath.flow.tool.system_tool import (
    RunShellCommandTool,
    WriteWorkspaceFileTool,
    flow_tool_code_run,
    flow_tool_command_run,
    flow_tool_files_exists,
    flow_tool_files_list,
    flow_tool_files_read,
    flow_tool_files_write,
    global_system_tools,
)
from rath.flow.tool.tool_table import (
    ToolNameConflictError,
    merge_tools_for_loop,
    tools_dict_to_schemas,
)

# Register built-in :class:`FlowToolCall` handlers for the session loop.
global_system_tools()

__all__ = [
    "BackendTool",
    "BackendToolCodeRun",
    "BackendToolCommandRun",
    "BackendToolFilesExists",
    "BackendToolFilesList",
    "BackendToolFilesRead",
    "BackendToolFilesWrite",
    "FlowToolCall",
    "RunShellCommandTool",
    "ToolNameConflictError",
    "WriteWorkspaceFileTool",
    "flow_tool_code_run",
    "flow_tool_command_run",
    "flow_tool_files_exists",
    "flow_tool_files_list",
    "flow_tool_files_read",
    "flow_tool_files_write",
    "global_system_tools",
    "merge_tools_for_loop",
    "tools_dict_to_schemas",
]
