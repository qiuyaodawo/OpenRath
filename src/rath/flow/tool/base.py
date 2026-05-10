"""Flow-layer tool abstraction: schema + :meth:`~FlowToolCall.__call__` execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from rath.session.session import Session

__all__ = ["FlowToolCall"]


class FlowToolCall(ABC):
    """User- or system-defined tool for the session loop (distinct from :class:`~rath.backend.tool_types.BackendTool`)."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def description(self) -> str | None:
        return None

    @property
    @abstractmethod
    def parameters(self) -> Mapping[str, Any]:
        """JSON Schema object for OpenAI ``parameters``."""

    @abstractmethod
    def __call__(self, session: Session, arguments: Mapping[str, Any]) -> Any:
        """Execute the tool. Sandbox tools may return :class:`~rath.backend.ToolResult` or ``bool``."""
