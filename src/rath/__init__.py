"""OpenRath: sandbox backends, LLM clients, and composable flow.

Sandbox dispatch uses :class:`~rath.backend.tool_types.BackendTool`. The session loop
uses :class:`~rath.flow.tool.FlowToolCall` as the flow-layer tool abstraction.

Import submodules explicitly, e.g. ``rath.flow.agent_param``; ``rath.session`` is
lazy-loaded via :func:`__getattr__`.
"""

from __future__ import annotations

from typing import Any

from rath import backend
from rath import flow

__all__ = ["backend", "flow", "session"]


def __getattr__(name: str) -> Any:
    """Lazy-load ``session`` on first attribute access."""
    if name == "session":
        from rath import session as _session

        return _session
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
