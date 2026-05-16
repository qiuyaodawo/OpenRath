"""Builders for the three record types in a persisted session JSONL stream.

Each line is a JSON object with a ``record_type`` discriminator:
``"header"``, ``"chunk"``, or ``"trailer"``.

JSONable projections for cumulative usage and lineage extras are reused from
:mod:`rath.session.graph.export` (which already ships those helpers for the
lineage-export pipeline). Only the persistence-specific shapes —
:class:`BackendSandboxSpec` round-trip and the header/chunk/trailer record
builders — live here. The module name keeps a leading underscore because
the on-disk file format is versioned via :data:`SCHEMA_VERSION` on the
header record; callers should go through
:class:`~rath.session.persistence.writer.SessionWriter` and
:func:`~rath.session.persistence.loader.load_session` rather than building
records by hand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from rath.backend.persistence.spec_json import (
    SCHEMA_VERSION,
    spec_from_jsonable,
    spec_to_jsonable,
)
from rath.llm.chat_response import RathLLMTokenUsage
from rath.session.chunk import ChunkRow
from rath.session.graph.export import (
    cumulative_usage_to_jsonable,
    lineage_extras_to_jsonable,
)
from rath.session.graph.kind import LineageKind
from rath.session.session import Session

__all__ = [
    "SCHEMA_VERSION",
    "build_header",
    "build_chunk_record",
    "build_trailer",
    "spec_to_jsonable",
    "spec_from_jsonable",
    "usage_from_jsonable",
    "lineage_extras_from_jsonable",
    "coerce_lineage_kind",
    "parse_uuid_list",
]


def _isoformat_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def usage_from_jsonable(raw: dict[str, Any] | None) -> RathLLMTokenUsage | None:
    """Inverse of :func:`rath.session.graph.export.cumulative_usage_to_jsonable`."""
    if raw is None:
        return None
    return RathLLMTokenUsage(
        prompt_tokens=int(raw.get("prompt_tokens", 0) or 0),
        completion_tokens=int(raw.get("completion_tokens", 0) or 0),
        total_tokens=int(raw.get("total_tokens", 0) or 0),
    )


def lineage_extras_from_jsonable(
    raw: list[Any] | None,
) -> tuple[tuple[str, Any], ...]:
    """Inverse of :func:`rath.session.graph.export.lineage_extras_to_jsonable`."""
    if not raw:
        return ()
    pairs: list[tuple[str, Any]] = []
    for entry in raw:
        if (
            isinstance(entry, (list, tuple))
            and len(entry) == 2
            and isinstance(entry[0], str)
        ):
            pairs.append((entry[0], entry[1]))
    return tuple(pairs)


def coerce_lineage_kind(value: Any) -> LineageKind:
    """Best-effort decode of ``lineage_kind`` string. Unknown → ``LineageKind.UNKNOWN``."""
    if isinstance(value, LineageKind):
        return value
    try:
        return LineageKind(value)
    except (ValueError, TypeError):
        return LineageKind.UNKNOWN


def parse_uuid_list(raw: list[Any] | None) -> tuple[UUID, ...]:
    """Decode a JSON list of UUID strings; drop any unparseable entry."""
    if not raw:
        return ()
    out: list[UUID] = []
    for entry in raw:
        try:
            out.append(UUID(str(entry)))
        except (ValueError, TypeError):
            continue
    return tuple(out)


def build_header(
    session: Session,
    *,
    sandbox_handle_id: str | None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the ``record_type=header`` dict for ``session``."""
    return {
        "record_type": "header",
        "schema_version": SCHEMA_VERSION,
        "id": str(session.id),
        "created_at": _isoformat_utc(created_at or datetime.now(timezone.utc)),
        "parent_session_ids": [str(p) for p in session.parent_session_ids],
        "lineage_operator": session.lineage_operator,
        "lineage_kind": session.lineage_kind.value,
        "lineage_extras": lineage_extras_to_jsonable(session.lineage_extras),
        "sandbox_backend": session.sandbox_backend,
        "sandbox_spec": spec_to_jsonable(session._sandbox_open_spec),
        "sandbox_handle_id": sandbox_handle_id,
    }


def build_chunk_record(index: int, row: ChunkRow) -> dict[str, Any]:
    return {
        "record_type": "chunk",
        "index": index,
        "kind": row.kind.value,
        "payload": row.payload,
    }


def build_trailer(
    session: Session,
    *,
    final_chunk_count: int,
    closed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "record_type": "trailer",
        "closed_at": _isoformat_utc(closed_at or datetime.now(timezone.utc)),
        "final_chunk_count": final_chunk_count,
        "cumulative_usage": cumulative_usage_to_jsonable(session),
    }
