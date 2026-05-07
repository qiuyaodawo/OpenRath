"""Factory for directory list payloads (→ :class:`~rath.backend.tool_types.BackendToolFilesList`)."""

from __future__ import annotations

from rath.backend.tool_types import BackendToolFilesList

__all__ = ["flow_tool_files_list"]


def flow_tool_files_list(path: str) -> BackendToolFilesList:
    """Build :class:`~rath.backend.tool_types.BackendToolFilesList`."""
    return BackendToolFilesList(path=path)
