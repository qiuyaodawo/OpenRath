"""Factory for shell-command tool payloads (→ :class:`~rath.backend.tool_types.BackendToolCommandRun`)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rath.backend.tool_types import BackendToolCommandRun

__all__ = ["flow_tool_command_run"]


def flow_tool_command_run(
    cmd: str | Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    stdin: bytes | None = None,
    timeout: float | None = None,
) -> BackendToolCommandRun:
    """Build :class:`~rath.backend.tool_types.BackendToolCommandRun`."""
    return BackendToolCommandRun(
        cmd=cmd, env=env, cwd=cwd, stdin=stdin, timeout=timeout
    )
