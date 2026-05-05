"""Backend ABC, ``BackendSandbox`` handle, and ``BackendSandboxSpec``.

The ``Backend`` ABC defines the unified flow-tool dispatch surface. The
single required runtime method is :meth:`Backend.dispatch`; everything else
is lifecycle (open / close) or static description (``is_available`` /
``capabilities`` / ``supported_calls``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

from rath.backend.core.capabilities import Capabilities
from rath.backend.core.errors import BackendSandboxClosed
from rath.backend.results.types import ToolResult
from rath.flow.tool import FlowToolCall

if TYPE_CHECKING:
    from rath.backend.stream import Stream


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
    """Backend-issued sandbox runtime handle.

    ``BackendSandbox`` is opaque: it carries the owning backend, an opaque
    ``handle`` string, and a closed flag. Behaviour lives in
    ``Backend.dispatch``; methods here are thin convenience wrappers.

    This type does **not** carry LLM or conversation state — that belongs in a
    future ``rath.Session`` layer, out of scope for this phase.
    """

    backend: "Backend"
    handle: str
    spec: BackendSandboxSpec | None = None
    closed: bool = field(default=False)

    async def __aenter__(self) -> "BackendSandbox":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if not self.closed:
            await self.backend.close(self)

    async def dispatch(self, call: FlowToolCall) -> ToolResult | bool:
        """Forward a flow tool call to the owning backend."""
        if self.closed:
            raise BackendSandboxClosed(self.handle)
        return await self.backend.dispatch(self, call)

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
    def supported_calls(cls) -> frozenset[type[FlowToolCall]]:
        """Return :class:`FlowToolCall` subclasses this backend handles."""

    @abstractmethod
    def sandbox_count(self) -> int:
        """Return the number of open sandboxes managed by this instance."""

    @abstractmethod
    async def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        """Open a fresh sandbox and return its handle."""

    @abstractmethod
    async def close(self, sandbox: BackendSandbox) -> None:
        """Close ``sandbox`` and release resources.

        Calling close on an already-closed sandbox is a no-op.
        """

    @abstractmethod
    async def dispatch(
        self, sandbox: BackendSandbox, call: FlowToolCall
    ) -> ToolResult | bool:
        """Execute ``call`` against ``sandbox`` and return its result.

        Implementations should raise
        :class:`~rath.backend.UnsupportedFlowToolCall` for call types not in
        :meth:`supported_calls`.
        """
