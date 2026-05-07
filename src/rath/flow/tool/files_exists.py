"""Factory for path-exists payloads (→ :class:`~rath.backend.tool_types.BackendToolFilesExists`)."""

from __future__ import annotations

from rath.backend.tool_types import BackendToolFilesExists

__all__ = ["flow_tool_files_exists"]


def flow_tool_files_exists(path: str) -> BackendToolFilesExists:
    """Build :class:`~rath.backend.tool_types.BackendToolFilesExists`."""
    return BackendToolFilesExists(path=path)
