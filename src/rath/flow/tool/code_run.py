"""Factory for code-interpreter payloads (→ :class:`~rath.backend.tool_types.BackendToolCodeRun`)."""

from __future__ import annotations

from rath.backend.tool_types import BackendToolCodeRun

__all__ = ["flow_tool_code_run"]


def flow_tool_code_run(
    code: str, *, language: str = "python", timeout: float | None = None
) -> BackendToolCodeRun:
    """Build :class:`~rath.backend.tool_types.BackendToolCodeRun`."""
    return BackendToolCodeRun(code=code, language=language, timeout=timeout)
