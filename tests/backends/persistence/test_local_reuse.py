"""End-to-end: alloc local sandbox id, write a file, close, reopen, file persists."""

from __future__ import annotations

from pathlib import Path

from rath.backend import get
from rath.backend.abc import BackendSandboxSpec
from rath.backend.persistence import PersistentSandboxRegistry
from rath.backend.tool_types import BackendToolFilesExists, BackendToolFilesWrite


def test_local_reuse_round_trip(_isolate_openrath_home: Path) -> None:
    """A persisted local working_dir survives ``close()`` and yields stored files on reopen."""
    reg = PersistentSandboxRegistry()
    sid = reg.alloc_local_id()
    workdir = reg.local_path(sid)
    backend = get("local")

    spec = BackendSandboxSpec(working_dir=str(workdir))

    # First open: write a marker file via the BackendTool API.
    with backend.open(spec) as sb:
        sb.dispatch(BackendToolFilesWrite(path="marker.txt", data="persisted"))

    # The directory still exists after close (user-supplied dir is never rmtree'd).
    assert workdir.is_dir()
    assert (workdir / "marker.txt").is_file()
    assert (workdir / "marker.txt").read_text(encoding="utf-8") == "persisted"

    # Second open with the SAME spec: the file is still there for dispatch.
    with backend.open(spec) as sb:
        exists = sb.dispatch(BackendToolFilesExists(path="marker.txt"))
        assert exists is True


def test_close_does_not_remove_persisted_workdir(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    sid = reg.alloc_local_id()
    workdir = reg.local_path(sid)
    backend = get("local")
    spec = BackendSandboxSpec(working_dir=str(workdir))
    with backend.open(spec) as sb:
        del sb  # noop; just exercising the lifecycle
    assert workdir.is_dir()


def test_list_local_includes_alloc_results(_isolate_openrath_home: Path) -> None:
    reg = PersistentSandboxRegistry()
    a = reg.alloc_local_id()
    b = reg.alloc_local_id()
    listed = reg.list_local()
    assert set(listed) >= {a, b}
