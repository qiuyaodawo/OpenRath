"""Factory for files.write payloads (→ :class:`~rath.backend.tool_types.BackendToolFilesWrite`)."""

from __future__ import annotations

from rath.backend.tool_types import BackendToolFilesWrite

__all__ = ["flow_tool_files_write"]


def flow_tool_files_write(
    path: str, data: bytes | str, *, mode: int = 0o644
) -> BackendToolFilesWrite:
    """Build :class:`~rath.backend.tool_types.BackendToolFilesWrite`."""
    return BackendToolFilesWrite(path=path, data=data, mode=mode)
