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

import uuid
from dataclasses import dataclass
from typing import Any

from rath.memory.abc import MemoryBackend, MemoryStore, MemoryStoreSpec
from rath.memory.capabilities import MemoryCapabilities, ScopeModel
from rath.memory.errors import MemoryBackendError, MemoryStoreClosed, UnsupportedMemoryOp
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


@dataclass
class _OpenVikingHandle:
    """Internal binding between a :class:`MemoryStore` handle and an SDK client."""

    client: Any
    mode: str  # "http" or "embedded"


@register("openviking")
class OpenVikingBackend(MemoryBackend):
    """:class:`~rath.memory.MemoryBackend` backed by OpenViking 0.3.x."""

    def __init__(self) -> None:
        self._handles: dict[str, _OpenVikingHandle] = {}

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
        return len(self._handles)

    def open(self, spec: MemoryStoreSpec | None = None) -> MemoryStore:
        spec = spec or MemoryStoreSpec()
        options = dict(spec.options or {})

        url = options.get("url")
        if url:
            try:
                client = _ov.SyncHTTPClient(
                    url=url,
                    api_key=options.get("api_key"),
                    account=spec.account_id or "default",
                    user_id=spec.user_id or "default",
                    agent_id=spec.agent_id or "default",
                    timeout=float(options.get("timeout", 60.0)),
                )
                client.initialize()
            except Exception as exc:  # noqa: BLE001 -- surface real cause
                raise MemoryBackendError(
                    f"failed to open OpenViking HTTP client at {url}: {exc}"
                ) from exc
            mode = "http"
        else:
            path = options.get("path")
            if not path:
                raise MemoryBackendError(
                    "MemoryStoreSpec.options must carry either 'url' (HTTP mode) or "
                    "'path' (embedded mode)"
                )
            try:
                client = _ov.OpenViking(path=str(path))
            except ImportError as exc:
                raise MemoryBackendError(
                    "openviking embedded mode requires the pyagfs binding-client "
                    f"wheel: {exc}"
                ) from exc
            except Exception as exc:  # noqa: BLE001
                raise MemoryBackendError(
                    f"failed to open OpenViking embedded client at {path}: {exc}"
                ) from exc
            mode = "embedded"

        handle = uuid.uuid4().hex
        self._handles[handle] = _OpenVikingHandle(client=client, mode=mode)
        return MemoryStore(backend=self, handle=handle, spec=spec)

    def close(self, store: MemoryStore) -> None:
        if store.closed:
            return
        entry = self._handles.pop(store.handle, None)
        if entry is not None:
            try:
                entry.client.close()
            except Exception:  # noqa: BLE001 -- close must be best-effort
                pass
        store.closed = True

    def dispatch(self, store: MemoryStore, op: MemoryOp) -> MemoryResult:
        if store.closed:
            raise MemoryStoreClosed(store.handle)
        if type(op) not in _SUPPORTED_OPS:
            raise UnsupportedMemoryOp(op_type=type(op))
        raise NotImplementedError(
            "OpenVikingBackend.dispatch implementation lands in tasks 2.4-2.6"
        )
