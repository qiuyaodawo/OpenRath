"""Schema migration scaffold round-trip + future-version refusal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rath.session.chunk import ChunkTable
from rath.session.persistence import (
    CURRENT_SCHEMA_VERSION,
    PersistenceError,
    SessionWriter,
    load_session,
    register_header_migration,
)
from rath.session.session import Session


def test_current_schema_round_trips_without_migration(
    _isolate_openrath_home: Path,
) -> None:
    s = Session(chunk_table=ChunkTable(rows=()))
    with SessionWriter(s) as w:
        from rath.session.chunk import user_text_chunk

        w.write_chunk(0, user_text_chunk("hi"))
    loaded = load_session(s.id)
    assert loaded.header.schema_version == CURRENT_SCHEMA_VERSION


def test_loader_refuses_newer_schema_version(
    _isolate_openrath_home: Path, tmp_path: Path
) -> None:
    """A file from a hypothetical OpenRath v2 (schema 99) must fail loudly."""
    cfg = tmp_path / "future.jsonl"
    cfg.write_text(
        json.dumps(
            {
                "record_type": "header",
                "schema_version": 99,
                "id": "ff07e08b-8504-4f8a-b306-a6227490d99e",
                "created_at": "2026-05-16T00:00:00+00:00",
                "parent_session_ids": [],
                "lineage_operator": "implicit",
                "lineage_kind": "unknown",
                "lineage_extras": [],
                "sandbox_backend": None,
                "sandbox_spec": None,
                "sandbox_handle_id": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PersistenceError, match="newer than CURRENT_SCHEMA_VERSION"):
        load_session("ff07e08b-8504-4f8a-b306-a6227490d99e", path=cfg)


def test_register_header_migration_rejects_current_or_above(
    _isolate_openrath_home: Path,
) -> None:
    with pytest.raises(ValueError, match="refusing to register"):
        register_header_migration(CURRENT_SCHEMA_VERSION, lambda r: r)
