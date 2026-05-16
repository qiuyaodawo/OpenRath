"""Schema migration scaffold for persisted session records.

Each ``record_type=header`` carries ``schema_version: int``. When the loader
sees a version lower than :data:`CURRENT_SCHEMA_VERSION`, it walks the
:data:`_MIGRATIONS` chain in order, calling each migrator with the in-memory
record dict and accepting the upgraded dict as the next input.

Currently there is only one version (``1``), so no migrators are registered.
The scaffold is in place so future bumps can add a function and a
``register_header_migration(from_version, fn)`` call without touching the
loader.

A migrator must NOT touch the file on disk — the loader keeps a single
read of the JSONL stream, applies migrators in-memory, and lets the caller
re-save (which writes the file with the current ``schema_version``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rath.session.persistence._serialize import SCHEMA_VERSION as CURRENT_SCHEMA_VERSION

__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "HeaderMigration",
    "ChunkMigration",
    "register_header_migration",
    "register_chunk_migration",
    "upgrade_header",
    "upgrade_chunk",
]

HeaderMigration = Callable[[dict[str, Any]], dict[str, Any]]
ChunkMigration = Callable[[dict[str, Any]], dict[str, Any]]

# Migrations keyed by the source version; running fn moves the record to
# ``source_version + 1``. The loader walks the chain until it reaches
# ``CURRENT_SCHEMA_VERSION``.
_HEADER_MIGRATIONS: dict[int, HeaderMigration] = {}
_CHUNK_MIGRATIONS: dict[int, ChunkMigration] = {}


def register_header_migration(from_version: int, fn: HeaderMigration) -> None:
    """Register a header migrator from ``from_version`` to ``from_version + 1``."""
    if from_version >= CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"refusing to register migration from version {from_version} >= "
            f"CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}",
        )
    _HEADER_MIGRATIONS[from_version] = fn


def register_chunk_migration(from_version: int, fn: ChunkMigration) -> None:
    """Register a chunk migrator from ``from_version`` to ``from_version + 1``.

    Chunk migrators are looked up using the **header**'s schema_version (the
    chunk records don't carry a version of their own — they share the
    header's).
    """
    if from_version >= CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"refusing to register migration from version {from_version} >= "
            f"CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}",
        )
    _CHUNK_MIGRATIONS[from_version] = fn


def upgrade_header(record: dict[str, Any]) -> dict[str, Any]:
    """Walk migrators until ``record["schema_version"] == CURRENT_SCHEMA_VERSION``.

    Raises :class:`ValueError` when no migrator is registered for an
    intermediate version (i.e. the file came from a newer OpenRath, or the
    chain has a gap).
    """
    current = int(record.get("schema_version", 0))
    while current < CURRENT_SCHEMA_VERSION:
        migrator = _HEADER_MIGRATIONS.get(current)
        if migrator is None:
            raise ValueError(
                f"no header migrator registered for schema_version={current}; "
                f"file may be from a newer OpenRath release",
            )
        record = migrator(record)
        current += 1
        record["schema_version"] = current
    if current > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"persisted file declares schema_version={current} which is "
            f"newer than CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION}; "
            f"refusing to downgrade",
        )
    return record


def upgrade_chunk(record: dict[str, Any], *, header_version: int) -> dict[str, Any]:
    """Apply per-version chunk migrators starting at ``header_version``.

    The header is already at ``CURRENT_SCHEMA_VERSION`` by the time the
    loader calls this; ``header_version`` is the **original** version it
    came in as, used to pick the right migrators in order.
    """
    current = header_version
    while current < CURRENT_SCHEMA_VERSION:
        migrator = _CHUNK_MIGRATIONS.get(current)
        if migrator is not None:
            record = migrator(record)
        current += 1
    return record
