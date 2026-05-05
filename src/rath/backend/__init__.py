"""Public API of :mod:`rath.backend`.

Re-exports the ABCs, value types, registry helpers and built-in backends. The
``local`` backend is imported eagerly (it is dependency-free) so that
``rath.backend.is_available("local")`` works without prior side-effects from
the caller.
"""

from __future__ import annotations

from rath.backend._abc import Backend, Sandbox, SandboxSpec
from rath.backend._calls import (
    CodeRun,
    CommandRun,
    FilesExists,
    FilesList,
    FilesRead,
    FilesWrite,
    ToolCall,
)
from rath.backend._capabilities import Capabilities, IsolationLevel
from rath.backend._errors import (
    BackendError,
    BackendNotFound,
    SandboxClosed,
    UnsupportedToolCall,
)
from rath.backend._registry import (
    current,
    get,
    get_class,
    is_available,
    list_names,
    preferred,
    register,
    set_default,
)
from rath.backend._results import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
    FileEntry,
    FileWriteResult,
    ToolResult,
)
from rath.backend._stream import Event, Future, Stream

# Eagerly register the built-in backends. ``local`` has no extra deps; the
# ``opensandbox`` adapter import is guarded so the package stays usable when
# the optional extra is not installed.
from rath.backend import local as _local  # noqa: F401

try:
    from rath.backend import opensandbox as _opensandbox  # noqa: F401
except ImportError:  # pragma: no cover - exercised when extra is missing
    pass

__all__ = [
    # ABC + handles
    "Backend",
    "Sandbox",
    "SandboxSpec",
    # Tool calls
    "ToolCall",
    "CommandRun",
    "FilesRead",
    "FilesWrite",
    "FilesList",
    "FilesExists",
    "CodeRun",
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
    "SandboxClosed",
    "UnsupportedToolCall",
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
