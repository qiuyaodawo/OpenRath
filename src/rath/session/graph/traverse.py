"""Pure graph helpers keyed by ``Session.parent_session_ids``."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterator, Mapping, Protocol, runtime_checkable
from uuid import UUID

from rath.session.graph.kind import LineageConsistencyError


@runtime_checkable
class _LineageCarrier(Protocol):
    id: UUID
    parent_session_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class FrozenLineageView:
    """Projection of lineage fields only (tests / exporters)."""

    session_id: UUID
    parent_session_ids: tuple[UUID, ...]
    lineage_operator: str
    lineage_kind_str: str
    lineage_extras: tuple[tuple[str, object], ...]


def lineage_view_dataclass(carrier: object) -> FrozenLineageView:
    """Best-effort read of lineage attributes on a duck-typed object."""
    if not isinstance(carrier, _LineageCarrier):
        raise TypeError("carrier must expose id and parent_session_ids")
    lk = getattr(carrier, "lineage_kind", None)
    kind_str = getattr(lk, "value", str(lk))
    return FrozenLineageView(
        session_id=carrier.id,
        parent_session_ids=tuple(carrier.parent_session_ids),
        lineage_operator=str(getattr(carrier, "lineage_operator", "")),
        lineage_kind_str=str(kind_str),
        lineage_extras=tuple(tuple(p) for p in getattr(carrier, "lineage_extras", ())),
    )


def ancestors_bfs(
    by_id: Mapping[UUID, _LineageCarrier],
    start_id: UUID,
) -> tuple[UUID, ...]:
    """Walk upward from ``start_id`` via ``parent_session_ids`` (nearest first)."""

    if start_id not in by_id:
        raise LineageConsistencyError(f"unknown session id in graph: {start_id}")
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    queue: deque[UUID] = deque(by_id[start_id].parent_session_ids)
    while queue:
        pid = queue.popleft()
        if pid in seen:
            continue
        if pid not in by_id:
            raise LineageConsistencyError(
                f"parent {pid} not in registry for descendant chain from {start_id}",
            )
        seen.add(pid)
        ordered.append(pid)
        queue.extend(by_id[pid].parent_session_ids)
    return tuple(ordered)


def descendants_dfs_preorder(
    by_id: Mapping[UUID, _LineageCarrier],
    root_id: UUID,
) -> tuple[UUID, ...]:
    """All descendants of ``root_id`` (children first DFS preorder)."""

    if root_id not in by_id:
        raise LineageConsistencyError(f"unknown root session id: {root_id}")

    adj: dict[UUID, list[UUID]] = {}
    for sid, sess in by_id.items():
        for p in sess.parent_session_ids:
            adj.setdefault(p, []).append(sid)

    out: list[UUID] = []
    stack = list(adj.get(root_id, ()))
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(reversed(adj.get(cur, ())))
    return tuple(dict.fromkeys(out))


def validate_acyclic(by_id: Mapping[UUID, _LineageCarrier]) -> None:
    """Raise ``LineageConsistencyError`` if parents are missing or the graph cycles."""

    for sid, sess in by_id.items():
        for p in sess.parent_session_ids:
            if p not in by_id:
                raise LineageConsistencyError(
                    f"{sid} references missing parent {p}",
                )

    _GRAY, _BLACK = 1, 2
    marks: dict[UUID, int] = {}

    def _visit(cur: UUID) -> None:
        stat = marks.get(cur, 0)
        if stat == _BLACK:
            return
        if stat == _GRAY:
            raise LineageConsistencyError(f"cycle involving session {cur}")
        marks[cur] = _GRAY
        for p in by_id[cur].parent_session_ids:
            _visit(p)
        marks[cur] = _BLACK

    for node in tuple(by_id):
        if marks.get(node, 0) == 0:
            _visit(node)


def edge_pairs(by_id: Mapping[UUID, _LineageCarrier]) -> Iterator[tuple[UUID, UUID]]:
    """Yield ``(producer, consumer)`` for each parent edge."""
    for sid, sess in by_id.items():
        for p in sess.parent_session_ids:
            yield p, sid


__all__ = [
    "FrozenLineageView",
    "ancestors_bfs",
    "descendants_dfs_preorder",
    "edge_pairs",
    "lineage_view_dataclass",
    "validate_acyclic",
]
