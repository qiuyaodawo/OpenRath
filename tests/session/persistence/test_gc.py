"""GC helpers: delete_session / prune_sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rath.session.chunk import ChunkTable, user_text_chunk
from rath.session.persistence import (
    SessionWriter,
    delete_session,
    list_persisted_sessions,
    prune_sessions,
    session_file,
)
from rath.session.session import Session


def _write_session(content: str = "hi") -> Session:
    s = Session(chunk_table=ChunkTable(rows=()))
    with SessionWriter(s) as w:
        w.write_chunk(0, user_text_chunk(content))
    return s


def test_delete_session_removes_file(_isolate_openrath_home: Path) -> None:
    s = _write_session()
    assert session_file(s.id).is_file()
    assert delete_session(s.id) is True
    assert not session_file(s.id).is_file()


def test_delete_session_returns_false_when_absent(
    _isolate_openrath_home: Path,
) -> None:
    import uuid

    assert delete_session(uuid.uuid4()) is False


def test_delete_session_is_idempotent(_isolate_openrath_home: Path) -> None:
    s = _write_session()
    assert delete_session(s.id) is True
    assert delete_session(s.id) is False


def test_prune_sessions_removes_only_older_than_cutoff(
    _isolate_openrath_home: Path,
) -> None:
    old = _write_session("old one")
    new = _write_session("new one")

    # Rewrite the old session's header timestamp to long ago by editing the
    # file directly — this is the cleanest way to simulate "older than".
    import json

    old_path = session_file(old.id)
    lines = old_path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    ancient = datetime.now(timezone.utc) - timedelta(days=400)
    header["created_at"] = ancient.isoformat()
    lines[0] = json.dumps(header, ensure_ascii=False)
    old_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    removed = prune_sessions(older_than=timedelta(days=30))
    assert removed == [old.id]
    surviving = {m.id for m in list_persisted_sessions()}
    assert surviving == {new.id}


def test_prune_sessions_empty_when_nothing_old(_isolate_openrath_home: Path) -> None:
    _write_session("fresh")
    assert prune_sessions(older_than=timedelta(days=30)) == []


def test_prune_sessions_skips_unparseable_files(
    _isolate_openrath_home: Path,
) -> None:
    """Files that don't parse aren't pruned (manual cleanup is safer)."""
    from rath.session.persistence.paths import ensure_sessions_dir

    target_dir = ensure_sessions_dir()
    junk = target_dir / "not-a-uuid.jsonl"
    junk.write_text("garbage\n", encoding="utf-8")
    # Should not raise; just returns empty.
    removed = prune_sessions(older_than=timedelta(seconds=0))
    assert removed == []
    assert junk.is_file()


@pytest.mark.parametrize("days", [1, 7, 365])
def test_prune_sessions_respects_arbitrary_cutoffs(
    _isolate_openrath_home: Path, days: int
) -> None:
    s = _write_session("s")
    import json

    path = session_file(s.id)
    lines = path.read_text(encoding="utf-8").splitlines()
    header = json.loads(lines[0])
    header["created_at"] = (
        datetime.now(timezone.utc) - timedelta(days=days + 1)
    ).isoformat()
    lines[0] = json.dumps(header, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    removed = prune_sessions(older_than=timedelta(days=days))
    assert removed == [s.id]
