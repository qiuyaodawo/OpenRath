"""Memory-backend abstract base, store handle, and store spec.

Parallel to :mod:`rath.backend.abc`: :class:`MemoryStore` mirrors
:class:`~rath.backend.abc.BackendSandbox` (refcount handle), and
:class:`MemoryStoreSpec` mirrors
:class:`~rath.backend.abc.BackendSandboxSpec`. The :class:`MemoryBackend`
ABC itself lands in the next task.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING

from rath.memory.errors import MemoryStoreClosed

if TYPE_CHECKING:
    from rath.memory.abc import MemoryBackend  # noqa: F401  (forward ref placeholder)


__all__ = ["MemoryStoreSpec", "MemoryStore"]


@dataclass
class MemoryStoreSpec:
    """User-facing description of a memory store to open.

    All fields are optional; backends may ignore fields that do not apply
    (e.g. an embedded backend ignores ``account_id``/``user_id``).
    """

    namespace: str | None = None
    account_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    options: Mapping[str, str] | None = None


@dataclass
class MemoryStore:
    """Memory store handle with reference counting.

    Lifecycle mirrors :class:`~rath.backend.abc.BackendSandbox`: each
    :class:`~rath.flow.Agent` slot, each ``with store:`` block, and any
    explicit :meth:`acquire` counts as one reference. :meth:`release`
    decrements and, when the count reaches zero, calls
    ``backend.close(self)``. There is no "force close" path -- callers that
    want immediate teardown must drop all references.

    :func:`MemoryBackend.open` returns a store with ``_refcount == 0``. The
    caller is expected to either bind it to an :class:`~rath.flow.Agent`
    (which acquires) or enter ``with store:`` (which acquires) before it can
    be safely held.
    """

    backend: "MemoryBackend"
    handle: str
    spec: MemoryStoreSpec | None = None
    closed: bool = field(default=False)
    _refcount: int = field(default=0, repr=False)

    @property
    def refcount(self) -> int:
        """Current number of live references; read-only mirror of internal state."""
        return self._refcount

    def acquire(self) -> "MemoryStore":
        """Add one reference; return ``self`` for chaining."""
        if self.closed:
            raise MemoryStoreClosed(self.handle)
        self._refcount += 1
        return self

    def release(self) -> None:
        """Drop one reference; close via the backend when the count hits zero."""
        if self.closed:
            return
        self._refcount -= 1
        if self._refcount <= 0:
            self.backend.close(self)

    def __enter__(self) -> "MemoryStore":
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
