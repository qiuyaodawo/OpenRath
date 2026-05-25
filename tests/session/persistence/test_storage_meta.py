"""Session persistence storage metadata: paths, migrations, write lock, sandbox reattach.

Consolidated from (every test function name preserved verbatim):
- test_paths.py             (path resolution)
- test_migrations.py        (schema version round-trip + future refusal)
- test_write_lock.py        (cross-process advisory lock)
- test_resume_reattach.py   (sandbox reattach via PersistentSandboxRegistry; opensandbox)
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from rath.backend import get
from rath.backend.persistence.registry import PersistentSandboxRegistry
from rath.session.chunk import ChunkTable, user_text_chunk
from rath.session.persistence import (
    CURRENT_SCHEMA_VERSION,
    PersistenceError,
    SessionWriter,
    load_session,
    register_header_migration,
)
from rath.session.persistence.paths import (
    SESSION_FILE_SUFFIX,
    SESSIONS_DIR_NAME,
    ensure_sessions_dir,
    session_file,
    sessions_dir,
)
from rath.session.session import Session
from tests.conftest import opensandbox_real

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def test_sessions_dir_under_openrath_home(_isolate_openrath_home: Path) -> None:
    expected = _isolate_openrath_home.resolve() / SESSIONS_DIR_NAME
    assert sessions_dir() == expected
    # Not created until ensure_sessions_dir is called.
    assert not sessions_dir().exists()


def test_session_file_deterministic(_isolate_openrath_home: Path) -> None:
    sid = uuid4()
    path = session_file(sid)
    assert path.name == f"{sid}{SESSION_FILE_SUFFIX}"
    assert path.parent == sessions_dir()


def test_session_file_accepts_string_id(_isolate_openrath_home: Path) -> None:
    sid = uuid4()
    via_uuid = session_file(sid)
    via_str = session_file(str(sid))
    assert via_uuid == via_str


def test_ensure_sessions_dir_creates_target(_isolate_openrath_home: Path) -> None:
    target = ensure_sessions_dir()
    assert target.is_dir()
    # Idempotent.
    again = ensure_sessions_dir()
    assert again == target


# ---------------------------------------------------------------------------
# migrations / schema version
# ---------------------------------------------------------------------------


def test_current_schema_round_trips_without_migration(
    _isolate_openrath_home: Path,
) -> None:
    s = Session(chunk_table=ChunkTable(rows=()))
    with SessionWriter(s) as w:
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


# ---------------------------------------------------------------------------
# cross-process advisory write lock
# ---------------------------------------------------------------------------


def test_second_writer_against_same_id_fails(
    _isolate_openrath_home: Path,
) -> None:
    s = Session(chunk_table=ChunkTable(rows=()))
    w1 = SessionWriter(s)
    w1.write_chunk(0, user_text_chunk("first"))
    # Same session id → same partial path; the second writer opens its
    # handle and grabs the lock during __init__, so the collision surfaces
    # at construction time rather than on first write.
    with pytest.raises(PersistenceError, match="another process"):
        SessionWriter(s)
    w1.close()


def test_lock_released_on_close_allows_reopen(
    _isolate_openrath_home: Path,
) -> None:
    s = Session(chunk_table=ChunkTable(rows=()))
    w1 = SessionWriter(s)
    w1.write_chunk(0, user_text_chunk("first"))
    w1.close()
    # After explicit close, reopening the same session id is allowed —
    # not a typical pattern, but it must not deadlock or false-fail.
    w2 = SessionWriter(s)
    w2.write_chunk(1, user_text_chunk("after close"))
    w2.close()


def test_lock_released_on_abandon_allows_reopen(
    _isolate_openrath_home: Path,
) -> None:
    s = Session(chunk_table=ChunkTable(rows=()))
    w1 = SessionWriter(s)
    w1.write_chunk(0, user_text_chunk("interrupted"))
    w1.abandon()
    w2 = SessionWriter(s)
    w2.write_chunk(1, user_text_chunk("after abandon"))
    w2.close()


def test_different_session_ids_dont_collide(_isolate_openrath_home: Path) -> None:
    s1 = Session(chunk_table=ChunkTable(rows=()))
    s2 = Session(chunk_table=ChunkTable(rows=()))
    w1 = SessionWriter(s1)
    w2 = SessionWriter(s2)
    w1.write_chunk(0, user_text_chunk("a"))
    w2.write_chunk(0, user_text_chunk("b"))
    w1.close()
    w2.close()


# ---------------------------------------------------------------------------
# opensandbox reattach round-trip
# ---------------------------------------------------------------------------


@opensandbox_real
@pytest.mark.opensandbox
def test_resume_reattaches_to_recorded_opensandbox() -> None:
    backend = get("opensandbox")
    sb = backend.open()
    sb.acquire()
    original_handle = sb.handle
    try:
        reg = PersistentSandboxRegistry()
        sandbox_uuid = reg.record_remote(
            backend="opensandbox",
            remote_id=sb.handle,
            spec=sb.spec,
        )

        s = Session(
            chunk_table=ChunkTable(rows=(user_text_chunk("hi"),)),
            sandbox_backend="opensandbox",
            _sandbox_open_spec=sb.spec,
        )
        with SessionWriter(s, sandbox_handle_id=str(sandbox_uuid)) as writer:
            writer.write_chunk(0, s.chunk_table.rows[0])

        loaded = load_session(s.id)
        assert loaded.header.sandbox_backend == "opensandbox"
        assert loaded.header.sandbox_handle_id == str(sandbox_uuid)

        user, _agent = loaded.to_resumable_pair()
        try:
            assert user.sandbox is not None, "resume should reattach the sandbox"
            assert user.sandbox.handle == original_handle, (
                "reattach must point at the same remote container"
            )
            assert user.sandbox is not sb, (
                "reattach should produce a new BackendSandbox handle object "
                "(refcount on the original is untouched)"
            )
        finally:
            user.close_sandbox()
    finally:
        sb.release()
