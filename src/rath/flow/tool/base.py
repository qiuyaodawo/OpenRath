"""Aliases for sandbox tool payloads (:class:`~rath.backend.tool_types.BackendTool`)."""

from __future__ import annotations

from typing import TypeAlias

from rath.backend.tool_types import BackendTool

FlowToolCall: TypeAlias = BackendTool

__all__ = ["BackendTool", "FlowToolCall"]
