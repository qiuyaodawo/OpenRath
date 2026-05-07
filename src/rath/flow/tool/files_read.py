"""Factory for files.read payloads (→ :class:`~rath.backend.tool_types.BackendToolFilesRead`)."""

from __future__ import annotations

from rath.backend.tool_types import BackendToolFilesRead

__all__ = ["flow_tool_files_read"]


def flow_tool_files_read(
    path: str, *, encoding: str | None = "utf-8"
) -> BackendToolFilesRead:
    """Build :class:`~rath.backend.tool_types.BackendToolFilesRead`."""
    return BackendToolFilesRead(path=path, encoding=encoding)
