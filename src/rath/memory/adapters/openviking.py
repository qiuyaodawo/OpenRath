"""OpenViking memory backend adapter (optional ``openrath[openviking]`` extra).

Wraps :class:`openviking.SyncHTTPClient` (HTTP mode) and
:class:`openviking.OpenViking` (embedded mode, conditional on the
``pyagfs`` binding-client wheel being available) behind a
:class:`~rath.memory.MemoryBackend`.

The module imports ``openviking`` lazily; when the extra is missing the
import block at the bottom of :mod:`rath.memory.__init__` swallows the
``ImportError`` and ``OpenVikingBackend`` is simply not registered.
"""

from __future__ import annotations

from rath.memory.abc import MemoryBackend, MemoryStore, MemoryStoreSpec
from rath.memory.capabilities import MemoryCapabilities, ScopeModel
from rath.memory.errors import UnsupportedMemoryOp
from rath.memory.op_types import (
    MemoryOp,
    MemoryOpCommit,
    MemoryOpFind,
    MemoryOpList,
    MemoryOpRead,
    MemoryOpResource,
    MemoryOpSearch,
    MemoryOpTree,
    MemoryOpWrite,
)
from rath.memory.registry import register
from rath.memory.results import MemoryResult

# Importing ``openviking`` is what gates this adapter; failures here propagate
# up to ``rath.memory.__init__``'s try/except so the registry stays empty when
# the optional extra is not installed.
import openviking as _ov  # noqa: F401  -- the import itself is the availability check


__all__ = ["OpenVikingBackend"]


_CAPABILITIES = MemoryCapabilities(
    scope_model=ScopeModel.HYBRID,
    supports_write=True,
    supports_read=True,
    supports_list=True,
    supports_tree=True,
    supports_vector_search=True,
    supports_intent_search=True,
    supports_resource_ingest=True,
    supports_session_commit=True,
    supports_l0_l1_l2=True,
)

_SUPPORTED_OPS: frozenset[type[MemoryOp]] = frozenset(
    {
        MemoryOpWrite,
        MemoryOpRead,
        MemoryOpList,
        MemoryOpTree,
        MemoryOpFind,
        MemoryOpSearch,
        MemoryOpResource,
        MemoryOpCommit,
    }
)


@register("openviking")
class OpenVikingBackend(MemoryBackend):
    """:class:`~rath.memory.MemoryBackend` backed by OpenViking 0.3.x."""

    @classmethod
    def is_available(cls) -> bool:
        return True  # Reaching this class means ``import openviking`` succeeded.

    @classmethod
    def capabilities(cls) -> MemoryCapabilities:
        return _CAPABILITIES

    @classmethod
    def supported_ops(cls) -> frozenset[type[MemoryOp]]:
        return _SUPPORTED_OPS

    def store_count(self) -> int:
        raise NotImplementedError("OpenVikingBackend.store_count lands in task 2.3")

    def open(self, spec: MemoryStoreSpec | None = None) -> MemoryStore:
        raise NotImplementedError("OpenVikingBackend.open lands in task 2.3")

    def close(self, store: MemoryStore) -> None:
        raise NotImplementedError("OpenVikingBackend.close lands in task 2.3")

    def dispatch(self, store: MemoryStore, op: MemoryOp) -> MemoryResult:
        if type(op) not in _SUPPORTED_OPS:
            raise UnsupportedMemoryOp(op_type=type(op))
        raise NotImplementedError(
            "OpenVikingBackend.dispatch implementation lands in tasks 2.4-2.6"
        )
