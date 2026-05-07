"""Backend-related exceptions."""

from __future__ import annotations


class BackendError(RuntimeError):
    """Base class for all rath.backend errors."""


class UnsupportedBackendTool(BackendError):
    """Raised when a backend cannot service a given :class:`~rath.backend.tool_types.BackendTool` type."""

    def __init__(self, call_type: type, backend_name: str) -> None:
        self.call_type = call_type
        self.backend_name = backend_name
        super().__init__(
            f"backend {backend_name!r} does not support backend tool payload "
            f"{call_type.__name__!r}"
        )

    def __reduce__(self) -> tuple[type, tuple[type, str]]:
        return (self.__class__, (self.call_type, self.backend_name))


class BackendSandboxClosed(BackendError):
    """Raised when dispatch is attempted on an already-closed backend sandbox."""

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"backend sandbox {handle!r} is already closed")

    def __reduce__(self) -> tuple[type, tuple[str]]:
        return (self.__class__, (self.handle,))


class BackendNotFound(BackendError):
    """Raised when a backend is requested by name but no such backend is registered."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"backend {name!r} is not registered; available backends: {available!r}"
        )

    def __reduce__(self) -> tuple[type, tuple[str, list[str]]]:
        return (self.__class__, (self.name, self.available))
