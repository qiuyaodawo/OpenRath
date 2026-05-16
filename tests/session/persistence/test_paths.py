"""Path resolution for persisted sessions."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from rath.session.persistence.paths import (
    SESSION_FILE_SUFFIX,
    SESSIONS_DIR_NAME,
    ensure_sessions_dir,
    session_file,
    sessions_dir,
)


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
