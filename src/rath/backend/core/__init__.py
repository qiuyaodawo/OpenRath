"""Core backend protocols, sandbox handle, capabilities, and errors."""

from rath.backend.core.abc import Backend, BackendSandbox, BackendSandboxSpec
from rath.backend.core.capabilities import Capabilities, IsolationLevel
from rath.backend.core.errors import (
    BackendError,
    BackendNotFound,
    BackendSandboxClosed,
    UnsupportedFlowToolCall,
)

__all__ = [
    "Backend",
    "BackendSandbox",
    "BackendSandboxSpec",
    "BackendError",
    "BackendNotFound",
    "BackendSandboxClosed",
    "UnsupportedFlowToolCall",
    "Capabilities",
    "IsolationLevel",
]
