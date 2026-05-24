"""Local filesystem memory backend.

Zero-runtime-dep memory backend so ``pip install openrath`` ships with a
working ``Agent(memory=...)`` path without requiring Docker, OpenViking, or
any extras. Persists every store under
``.openrath/memory/local/<uuid>/`` (see :mod:`rath.memory.persistence`).

This module contains the lifecycle skeleton: ``open`` / ``close`` /
``store_count`` / ``is_available`` / ``capabilities`` and a placeholder
``dispatch`` that returns ``unsupported`` for every op. Concrete op
handling lands in subsequent chunks (fs ops → find → resource → commit).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rath.memory.abc import MemoryBackend, MemoryStore, MemoryStoreSpec
from rath.memory.capabilities import MemoryCapabilities, ScopeModel
from rath.memory.errors import MemoryStoreClosed
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
from rath.memory.persistence import (
    PersistentMemoryRegistry,
    ensure_local_memory_root,
)
from rath.memory.registry import register
from rath.memory.results import MemoryExecutionFailure, MemoryResult

__all__ = ["LocalMemoryBackend", "META_SCHEMA_VERSION"]


META_SCHEMA_VERSION = 1
_META_FILENAME = "meta.json"


_CAPABILITIES = MemoryCapabilities(
    scope_model=ScopeModel.HYBRID,
    supports_write=True,
    supports_read=True,
    supports_list=True,
    supports_tree=True,
    supports_vector_search=True,
    supports_intent_search=False,
    supports_resource_ingest=True,
    supports_session_commit=True,
    supports_l0_l1_l2=False,
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
class _LocalHandle:
    """Internal binding: a :class:`MemoryStore` handle (str path) -> live state."""

    path: Path
    options: dict[str, Any]


@register("local")
class LocalMemoryBackend(MemoryBackend):
    """Filesystem-backed memory backend, default for ``pip install openrath``."""

    def __init__(self) -> None:
        self._handles: dict[str, _LocalHandle] = {}
        self._registry = PersistentMemoryRegistry()

    @classmethod
    def is_available(cls) -> bool:
        return True

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

        explicit = options.get("path")
        if explicit:
            path = Path(explicit).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
        else:
            ensure_local_memory_root()
            sid = self._registry.alloc_local_id()
            path = self._registry.local_path(sid).resolve()

        self._touch_meta(path, options=options)

        handle = str(path)
        self._handles[handle] = _LocalHandle(path=path, options=options)
        return MemoryStore(backend=self, handle=handle, spec=spec, closed=False)

    def close(self, store: MemoryStore) -> None:
        if store.closed:
            return
        bound = self._handles.pop(store.handle, None)
        if bound is not None:
            try:
                self._touch_meta(bound.path, options=bound.options, update_only=True)
            except OSError:
                pass
        store.closed = True

    def dispatch(self, store: MemoryStore, op: MemoryOp) -> MemoryResult:
        if store.closed:
            raise MemoryStoreClosed(store.handle)
        return MemoryExecutionFailure(
            kind="unsupported",
            message=(
                f"LocalMemoryBackend does not yet implement "
                f"{type(op).__name__}"
            ),
        )

    # ---------------------------------------------------------------- helpers

    def _touch_meta(
        self,
        path: Path,
        *,
        options: dict[str, Any],
        update_only: bool = False,
    ) -> None:
        meta_path = path / _META_FILENAME
        now = datetime.now(timezone.utc).isoformat()
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        else:
            meta = {}
        meta.setdefault("schema_version", META_SCHEMA_VERSION)
        meta.setdefault("created_at", now)
        meta["last_used_at"] = now
        if not update_only:
            meta["embedding_provider"] = options.get("embedding_provider")
            meta["vlm_provider"] = options.get("vlm_provider")
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
