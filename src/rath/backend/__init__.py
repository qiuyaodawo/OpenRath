"""Public API of :mod:`rath.backend`.

Re-exports the ABCs, value types, registry helpers and built-in backends. The
``local`` backend is imported eagerly (it is dependency-free) so that
``rath.backend.is_available("local")`` works without prior side-effects from
the caller.
"""

from __future__ import annotations

from rath.backend._calls import (
    FlowToolCall,
    FlowToolCodeRun,
    FlowToolCommandRun,
    FlowToolFilesExists,
    FlowToolFilesList,
    FlowToolFilesRead,
    FlowToolFilesWrite,
)
from rath.backend.core import (
    Backend,
    BackendSandbox,
    BackendSandboxSpec,
    BackendError,
    BackendNotFound,
    BackendSandboxClosed,
    Capabilities,
    IsolationLevel,
    UnsupportedFlowToolCall,
)
from rath.backend.registry import (
    current,
    get,
    get_class,
    is_available,
    list_names,
    preferred,
    register,
    set_default,
)
from rath.backend.results import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileEntry,
    FileWriteResult,
    ToolResult,
)
from rath.backend.stream import Event, Future, Stream

# Eagerly register the built-in backends. ``local`` has no extra deps; the
# ``opensandbox`` adapter import is guarded so the package stays usable when
# the optional extra is not installed.
from rath.backend.adapters import local as _local  # noqa: F401

try:
    from rath.backend.adapters import opensandbox as _opensandbox  # noqa: F401
except ImportError:  # pragma: no cover - exercised when extra is missing
    pass

__all__ = [
    # ABC + handles
    "Backend",
    "BackendSandbox",
    "BackendSandboxSpec",
    # Flow tool calls
    "FlowToolCall",
    "FlowToolCommandRun",
    "FlowToolFilesRead",
    "FlowToolFilesWrite",
    "FlowToolFilesList",
    "FlowToolFilesExists",
    "FlowToolCodeRun",
    # Tool results
    "ToolResult",
    "CommandResult",
    "FileContent",
    "FileEntry",
    "FileEntries",
    "FileWriteResult",
    "CodeResult",
    # Capabilities
    "Capabilities",
    "IsolationLevel",
    # Errors
    "BackendError",
    "BackendNotFound",
    "BackendSandboxClosed",
    "UnsupportedFlowToolCall",
    # Concurrency primitives
    "Stream",
    "Event",
    "Future",
    # Registry
    "register",
    "list_names",
    "get",
    "get_class",
    "is_available",
    "preferred",
    "set_default",
    "current",
]
