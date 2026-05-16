"""Real-fs tests for :class:`PersistentSandboxRegistry`."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

from rath.backend.abc import BackendSandboxSpec
from rath.backend.persistence import (
    PersistentSandboxRegistry,
    local_root,
    local_sandbox_dir,
    opensandbox_index_path,
    opensandbox_root,
)


def test_alloc_local_id_creates_directory(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.alloc_local_id()
    assert isinstance(sid, UUID)
    path = reg.local_path(sid)
    assert path == local_sandbox_dir(sid)
    assert path.is_dir()


def test_alloc_local_id_unique_per_call(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    a = reg.alloc_local_id()
    b = reg.alloc_local_id()
    assert a != b
    assert reg.local_path(a) != reg.local_path(b)


def test_ensure_local_idempotent(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = uuid4()
    first = reg.ensure_local(sid)
    second = reg.ensure_local(sid)
    assert first == second
    assert first.is_dir()


def test_list_local_enumerates_uuid_dirs(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    ids = {reg.alloc_local_id() for _ in range(3)}
    # Drop a non-UUID directory; it must be ignored.
    (local_root() / "garbage").mkdir(parents=True)
    listed = set(reg.list_local())
    assert listed == ids


def test_list_local_empty_when_dir_missing(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    assert reg.list_local() == []


def test_record_remote_writes_index_file(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    spec = BackendSandboxSpec(
        image="opensandbox/code-interpreter:v1.0.2",
        env={"FOO": "bar"},
        timeout=timedelta(seconds=600),
        working_dir="/workspace",
    )
    sid = reg.record_remote("opensandbox", "remote-id-xyz", spec)
    path = opensandbox_index_path(sid)
    assert path.is_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["backend"] == "opensandbox"
    assert raw["remote_id"] == "remote-id-xyz"
    assert raw["spec"]["working_dir"] == "/workspace"
    assert raw["spec"]["timeout_seconds"] == 600.0


def test_load_remote_round_trips_spec(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    spec = BackendSandboxSpec(working_dir="/ws", env={"K": "V"})
    sid = reg.record_remote("opensandbox", "rid-1", spec)
    rec = reg.load_remote(sid)
    assert rec is not None
    assert rec.backend == "opensandbox"
    assert rec.remote_id == "rid-1"
    assert rec.spec is not None
    assert rec.spec.working_dir == "/ws"
    assert rec.spec.env == {"K": "V"}


def test_load_remote_missing_returns_none(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    assert reg.load_remote(uuid4()) is None


def test_touch_remote_updates_last_used(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.record_remote("opensandbox", "rid-2", None)
    first = reg.load_remote(sid)
    assert first is not None
    import time

    time.sleep(0.005)
    reg.touch_remote(sid)
    second = reg.load_remote(sid)
    assert second is not None
    assert second.last_used_at >= first.last_used_at
    assert second.created_at == first.created_at


def test_list_remote_orders_by_created_at(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    a = reg.record_remote("opensandbox", "rid-a", None)
    import time

    time.sleep(0.005)
    b = reg.record_remote("opensandbox", "rid-b", None)
    rows = reg.list_remote()
    assert [r.id for r in rows] == [a, b]


def test_ensure_dirs_creates_both_roots(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    reg.ensure_dirs()
    assert local_root().is_dir()
    assert opensandbox_root().is_dir()
