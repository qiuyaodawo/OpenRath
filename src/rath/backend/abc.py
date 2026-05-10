"""Backend abstract base, sandbox handle, and sandbox spec."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from types import TracebackType
from typing import ClassVar

from rath.backend.capabilities import Capabilities
from rath.backend.errors import BackendSandboxClosed
from rath.backend.results import ToolResult
from rath.backend.tool_types import BackendTool


@dataclass
class BackendSandboxSpec:
    """User-facing description of a sandbox to open.

    Fields are intentionally optional. Each backend may ignore fields that do
    not apply (e.g. ``LocalBackend`` ignores ``image``).
    """

    image: str | None = None
    entrypoint: Sequence[str] | None = None
    env: Mapping[str, str] | None = None
    timeout: timedelta | None = None
    working_dir: str | None = None


@dataclass
class BackendSandbox:
    """Sandbox handle: owning :class:`Backend`, opaque ``handle``, and lifecycle flag."""

    backend: "Backend"
    handle: str
    spec: BackendSandboxSpec | None = None
    closed: bool = field(default=False)

    def __enter__(self) -> "BackendSandbox":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self.closed:
            self.backend.close(self)

    def dispatch(self, call: BackendTool) -> ToolResult | bool:
        """Apply ``call`` through :meth:`~rath.backend.abc.Backend.dispatch`."""
        if self.closed:
            raise BackendSandboxClosed(self.handle)
        return self.backend.dispatch(self, call)

    def stream(self, *, buffer: int = 0) -> "Stream":
        """Return a fresh :class:`Stream` bound to this sandbox.

        ``buffer=0`` (the default) means an unbounded queue; set a positive integer
        to apply backpressure on :meth:`Stream.submit`.
        """
        from rath.backend.stream import Stream

        return Stream(self, buffer=buffer)


class Backend(ABC):
    """Abstract base class for sandbox backends.

    Subclasses must:

    1. Set the ``name`` class attribute and register via
       :func:`rath.backend.register`.
    2. Implement the static ``is_available``, ``capabilities`` and
       ``supported_calls`` classmethods.
    3. Implement the instance methods ``sandbox_count``, ``open``, ``close``
       and ``dispatch``.
    """

    name: ClassVar[str]

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Return whether this backend is usable in the current environment.

        Must be cheap (microseconds, no network, no subprocess). Examples:
        check that a required SDK is importable, or that a config file or
        environment variable is present.
        """

    @classmethod
    @abstractmethod
    def capabilities(cls) -> Capabilities:
        """Return the static capability description of this backend type."""

    @classmethod
    @abstractmethod
    def supported_calls(cls) -> frozenset[type[BackendTool]]:
        """Return :class:`~rath.backend.tool_types.BackendTool` subclasses this backend handles."""

    @abstractmethod
    def sandbox_count(self) -> int:
        """Return the number of open sandboxes managed by this instance."""

    @abstractmethod
    def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        """Open a fresh sandbox and return its handle."""

    @abstractmethod
    def close(self, sandbox: BackendSandbox) -> None:
        """Close ``sandbox`` and release resources.

        Calling close on an already-closed sandbox is a no-op.
        """

    @abstractmethod
    def dispatch(
        self, sandbox: BackendSandbox, call: BackendTool
    ) -> ToolResult | bool:
        """Execute ``call`` against ``sandbox`` and return its result.

        Implementations should raise
        :class:`~rath.backend.UnsupportedBackendTool` for call types not in
        :meth:`supported_calls`.
        """
