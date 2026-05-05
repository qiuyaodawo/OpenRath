"""Backend ABC, ``Sandbox`` handle, and ``SandboxSpec``.

The ``Backend`` ABC defines the unified tool-call dispatch surface. The single
required runtime method is :meth:`Backend.dispatch`; everything else is
lifecycle (open / close) or static description (is_available / capabilities /
supported_calls).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

from rath.backend._calls import ToolCall
from rath.backend._capabilities import Capabilities
from rath.backend._errors import SandboxClosed
from rath.backend._results import ToolResult

if TYPE_CHECKING:
    from rath.backend._stream import Stream


@dataclass
class SandboxSpec:
    """User-facing description of a sandbox to open.

    Fields are intentionally optional. Each backend is free to ignore fields
    that don't apply (e.g. ``LocalBackend`` ignores ``image``).
    """

    image: str | None = None
    entrypoint: Sequence[str] | None = None
    env: Mapping[str, str] | None = None
    timeout: timedelta | None = None
    working_dir: str | None = None


@dataclass
class Sandbox:
    """A backend-issued runtime handle.

    ``Sandbox`` is an opaque handle: it carries the owning backend, an
    opaque ``handle`` string, and a closed flag. All real behaviour lives
    in ``Backend.dispatch``; the methods on this class are thin
    convenience wrappers.

    A ``Sandbox`` does **not** carry any LLM context or conversation
    state. Those concerns belong to a future ``rath.Session`` layer that
    is intentionally out of scope for this phase.
    """

    backend: "Backend"
    handle: str
    spec: SandboxSpec | None = None
    closed: bool = field(default=False)

    async def __aenter__(self) -> "Sandbox":
        return self

    async def __aexit__(self, *exc: object) -> None:
        if not self.closed:
            await self.backend.close(self)

    async def dispatch(self, call: ToolCall) -> ToolResult | bool:
        """Forward a tool call to the owning backend."""
        if self.closed:
            raise SandboxClosed(self.handle)
        return await self.backend.dispatch(self, call)

    def stream(self, *, buffer: int = 0) -> "Stream":
        """Return a fresh :class:`Stream` bound to this sandbox.

        ``buffer=0`` (default) means an unbounded queue; set a positive
        integer to apply backpressure on :meth:`Stream.submit`.
        """
        # Imported lazily to avoid a circular import: _stream depends on
        # this module's :class:`Sandbox`.
        from rath.backend._stream import Stream

        return Stream(self, buffer=buffer)


class Backend(ABC):
    """Abstract base class for sandbox backends.

    Subclasses must:

    1. Set the ``name`` class attribute and register via
       :func:`rath.backend.register`.
    2. Implement the static ``is_available``, ``capabilities`` and
       ``supported_calls`` classmethods.
    3. Implement the instance methods ``sandbox_count``, ``open``,
       ``close`` and ``dispatch``.
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
    def supported_calls(cls) -> frozenset[type[ToolCall]]:
        """Return the set of :class:`ToolCall` subclasses this backend handles."""

    @abstractmethod
    def sandbox_count(self) -> int:
        """Return the number of currently open sandboxes managed by this instance."""

    @abstractmethod
    async def open(self, spec: SandboxSpec | None = None) -> Sandbox:
        """Open a fresh sandbox and return its handle."""

    @abstractmethod
    async def close(self, sandbox: Sandbox) -> None:
        """Close ``sandbox`` and release its resources.

        Calling close on an already-closed sandbox is a no-op.
        """

    @abstractmethod
    async def dispatch(self, sandbox: Sandbox, call: ToolCall) -> ToolResult | bool:
        """Execute ``call`` against ``sandbox`` and return its result.

        Implementations should raise
        :class:`~rath.backend.UnsupportedToolCall` for call types not in
        :meth:`supported_calls`.
        """
