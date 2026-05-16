"""GC helpers for sandbox registry: delete_local / prune_local / delete_remote / prune_remote."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from rath.backend.abc import BackendSandboxSpec
from rath.backend.persistence import (
    PersistentSandboxRegistry,
    local_sandbox_dir,
    opensandbox_index_path,
)


def test_delete_local_removes_dir(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.alloc_local_id()
    assert reg.local_path(sid).is_dir()
    assert reg.delete_local(sid) is True
    assert not reg.local_path(sid).exists()


def test_delete_local_returns_false_when_absent(
    _isolate_openrath_home: Path,
) -> None:
    reg = PersistentSandboxRegistry()
    assert reg.delete_local(uuid4()) is False


def test_delete_local_removes_with_contents(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.alloc_local_id()
    (reg.local_path(sid) / "nested" / "deep").mkdir(parents=True)
    (reg.local_path(sid) / "nested" / "file.txt").write_text("x", encoding="utf-8")
    assert reg.delete_local(sid) is True
    assert not reg.local_path(sid).exists()


def test_prune_local_removes_only_old_dirs(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    old = reg.alloc_local_id()
    new = reg.alloc_local_id()
    # Backdate the old dir's mtime by a year.
    old_path = local_sandbox_dir(old)
    ancient = time.time() - 365 * 24 * 3600
    os.utime(old_path, (ancient, ancient))

    removed = reg.prune_local(older_than=timedelta(days=30))
    assert removed == [old]
    assert not old_path.exists()
    assert reg.local_path(new).is_dir()


def test_prune_local_empty_when_no_old_dirs(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    reg.alloc_local_id()
    assert reg.prune_local(older_than=timedelta(days=30)) == []


def test_delete_remote_removes_index(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.record_remote("opensandbox", "remote-1", None)
    assert opensandbox_index_path(sid).is_file()
    assert reg.delete_remote(sid) is True
    assert not opensandbox_index_path(sid).exists()


def test_delete_remote_returns_false_when_absent(
    _isolate_openrath_home: Path,
) -> None:
    reg = PersistentSandboxRegistry()
    assert reg.delete_remote(uuid4()) is False


def test_prune_remote_uses_last_used_at(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid_old = reg.record_remote("opensandbox", "rid-old", None)
    sid_new = reg.record_remote("opensandbox", "rid-new", None)

    # Rewrite the old record's last_used_at to long ago.
    import json

    path = opensandbox_index_path(sid_old)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["last_used_at"] = (
        datetime.now(timezone.utc) - timedelta(days=400)
    ).isoformat()
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    removed = reg.prune_remote(older_than=timedelta(days=30))
    assert removed == [sid_old]
    assert reg.load_remote(sid_new) is not None


def test_reattach_remote_missing_id_raises(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    with pytest.raises(KeyError, match="no remote sandbox"):
        reg.reattach_remote(uuid4())


def test_reattach_remote_unsupported_backend_raises(
    _isolate_openrath_home: Path,
) -> None:
    reg = PersistentSandboxRegistry()
    # ``local`` backend has no ``attach`` method.
    sid = reg.record_remote(
        "local", "rid-not-supported", BackendSandboxSpec(working_dir="/tmp/x")
    )
    with pytest.raises(AttributeError, match="does not support reattach"):
        reg.reattach_remote(sid)
