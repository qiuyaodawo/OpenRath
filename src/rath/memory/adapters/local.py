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
from rath.memory.errors import MemoryStoreClosed, UnsupportedMemoryOp
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
from rath.memory.results import (
    MemoryEntry,
    MemoryExecutionFailure,
    MemoryListResult,
    MemoryReadResult,
    MemoryResult,
    MemoryWriteResult,
)

__all__ = ["LocalMemoryBackend", "META_SCHEMA_VERSION"]


META_SCHEMA_VERSION = 1
_META_FILENAME = "meta.json"
_VIKING_PREFIX = "viking://"
_VALID_SCOPES: frozenset[str] = frozenset({"user", "agent", "session", "resources"})
_MD_SUFFIX = ".md"
_VEC_SUFFIX = ".vec"
_META_SUFFIX = ".meta.json"
_HIDDEN_SUFFIXES: frozenset[str] = frozenset({_VEC_SUFFIX, _META_SUFFIX})


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
        if type(op) not in _SUPPORTED_OPS:
            raise UnsupportedMemoryOp(op_type=type(op))
        bound = self._handles[store.handle]
        try:
            if isinstance(op, MemoryOpWrite):
                return self._dispatch_write(bound, op)
            if isinstance(op, MemoryOpRead):
                return self._dispatch_read(bound, op)
            if isinstance(op, MemoryOpList):
                return self._dispatch_list(bound, op)
            if isinstance(op, MemoryOpTree):
                return self._dispatch_tree(bound, op)
        except PermissionError as exc:
            return MemoryExecutionFailure(
                kind="unauthorized",
                message=f"permission denied: {exc}",
            )
        except OSError as exc:
            return MemoryExecutionFailure(
                kind="internal",
                message=f"{type(exc).__name__}: {exc}",
            )
        # Find / Search / Resource / Commit land in later chunks.
        return MemoryExecutionFailure(
            kind="unsupported",
            message=(
                f"LocalMemoryBackend does not yet implement "
                f"{type(op).__name__}"
            ),
        )

    # ---------------------------------------------------------------- FS handlers

    def _dispatch_write(
        self, bound: "_LocalHandle", op: MemoryOpWrite
    ) -> MemoryResult:
        resolved = _resolve_uri(bound.path, op.uri)
        if isinstance(resolved, MemoryExecutionFailure):
            return resolved
        if op.mode not in ("replace", "write"):
            return MemoryExecutionFailure(
                kind="unsupported",
                message=f"unsupported write mode: {op.mode!r}",
            )
        target = resolved.with_suffix(_MD_SUFFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = op.content
        target.write_text(data, encoding="utf-8")
        # Stale embedding/meta sidecars must not persist past a content rewrite.
        for suffix in _HIDDEN_SUFFIXES:
            sidecar = resolved.with_suffix(suffix)
            if sidecar.exists():
                sidecar.unlink()
        return MemoryWriteResult(
            uri=op.uri, bytes_written=len(data.encode("utf-8"))
        )

    def _dispatch_read(
        self, bound: "_LocalHandle", op: MemoryOpRead
    ) -> MemoryResult:
        resolved = _resolve_uri(bound.path, op.uri)
        if isinstance(resolved, MemoryExecutionFailure):
            return resolved
        target = resolved.with_suffix(_MD_SUFFIX)
        if not target.is_file():
            return MemoryExecutionFailure(
                kind="not_found",
                message=f"no memory at {op.uri}",
            )
        body = target.read_text(encoding="utf-8")
        data: str | bytes
        if op.encoding is None:
            data = body.encode("utf-8")
        else:
            data = body
        return MemoryReadResult(uri=op.uri, data=data, level=op.level)

    def _dispatch_list(
        self, bound: "_LocalHandle", op: MemoryOpList
    ) -> MemoryResult:
        resolved = _resolve_uri(bound.path, op.uri, must_be_dir=True)
        if isinstance(resolved, MemoryExecutionFailure):
            return resolved
        if not resolved.is_dir():
            return MemoryListResult(entries=())
        return MemoryListResult(entries=_list_dir(resolved, op.uri))

    def _dispatch_tree(
        self, bound: "_LocalHandle", op: MemoryOpTree
    ) -> MemoryResult:
        resolved = _resolve_uri(bound.path, op.uri, must_be_dir=True)
        if isinstance(resolved, MemoryExecutionFailure):
            return resolved
        if not resolved.is_dir():
            return MemoryListResult(entries=())
        flat: list[MemoryEntry] = []
        _walk_tree(resolved, op.uri, max_depth=op.depth, sink=flat)
        return MemoryListResult(entries=tuple(flat))

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


def _resolve_uri(
    store_root: Path, uri: str, *, must_be_dir: bool = False
) -> Path | MemoryExecutionFailure:
    """Map ``viking://{scope}/{rest}`` to a path under ``store_root``.

    Rejects unknown scopes, non-``viking://`` URIs, and any input that
    escapes ``store_root`` after resolution (path traversal guard). Returns
    the file path **without** the ``.md`` / ``.vec`` suffix — handlers
    append the right one.
    """
    if not uri.startswith(_VIKING_PREFIX):
        return MemoryExecutionFailure(
            kind="invalid_uri",
            message=f"URI must start with {_VIKING_PREFIX!r}: {uri!r}",
        )
    tail = uri[len(_VIKING_PREFIX):]
    if not tail:
        return MemoryExecutionFailure(
            kind="invalid_uri",
            message="URI has empty path after scheme",
        )
    parts = tail.split("/")
    scope = parts[0]
    if scope not in _VALID_SCOPES:
        return MemoryExecutionFailure(
            kind="invalid_uri",
            message=(
                f"unknown scope {scope!r}; must be one of "
                f"{sorted(_VALID_SCOPES)}"
            ),
        )
    rest = parts[1:]
    # Reject empty segments and any traversal token *before* resolving.
    for seg in rest:
        if seg in ("", ".", ".."):
            return MemoryExecutionFailure(
                kind="invalid_uri",
                message=f"forbidden path segment in {uri!r}",
            )
    candidate = store_root.joinpath(scope, *rest)
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return MemoryExecutionFailure(
            kind="invalid_uri",
            message=f"cannot resolve {uri!r}: {exc}",
        )
    root_resolved = store_root.resolve(strict=False)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return MemoryExecutionFailure(
            kind="invalid_uri",
            message=f"path escapes store root: {uri!r}",
        )
    return resolved


def _entry_for(path: Path, uri_base: str) -> MemoryEntry | None:
    """Build a :class:`MemoryEntry` for ``path``; ``None`` if it must be hidden."""
    name = path.name
    if name.endswith(_VEC_SUFFIX):
        return None
    if name == _META_FILENAME:
        return None
    if name.endswith(_META_SUFFIX):
        return None
    if path.is_dir():
        return MemoryEntry(
            name=name,
            uri=f"{uri_base.rstrip('/')}/{name}",
            is_dir=True,
            size=None,
        )
    if name.endswith(_MD_SUFFIX):
        display = name[: -len(_MD_SUFFIX)]
        size = path.stat().st_size if path.exists() else None
        return MemoryEntry(
            name=display,
            uri=f"{uri_base.rstrip('/')}/{display}",
            is_dir=False,
            size=size,
        )
    # Non-markdown files (e.g. resource originals) keep their name verbatim.
    size = path.stat().st_size if path.exists() else None
    return MemoryEntry(
        name=name,
        uri=f"{uri_base.rstrip('/')}/{name}",
        is_dir=False,
        size=size,
    )


def _list_dir(dir_path: Path, uri_base: str) -> tuple[MemoryEntry, ...]:
    entries: list[MemoryEntry] = []
    for child in sorted(dir_path.iterdir()):
        e = _entry_for(child, uri_base)
        if e is not None:
            entries.append(e)
    return tuple(entries)


def _walk_tree(
    dir_path: Path,
    uri_base: str,
    *,
    max_depth: int,
    sink: list[MemoryEntry],
    _depth: int = 0,
) -> None:
    """Pre-order walk emitting one :class:`MemoryEntry` per visible node.

    ``max_depth=0`` lists only the immediate children of ``dir_path``;
    ``max_depth=N`` recurses N additional levels.
    """
    if _depth > max_depth:
        return
    for child in sorted(dir_path.iterdir()):
        entry = _entry_for(child, uri_base)
        if entry is None:
            continue
        sink.append(entry)
        if entry.is_dir and _depth < max_depth:
            _walk_tree(
                child,
                entry.uri,
                max_depth=max_depth,
                sink=sink,
                _depth=_depth + 1,
            )
