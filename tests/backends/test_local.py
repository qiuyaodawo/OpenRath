"""Local-backend-only tests (always-on, temp and user-supplied working dirs)."""

from __future__ import annotations

import os

from rath.backend import (
    BackendSandboxSpec,
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
    IsolationLevel,
    ToolExecutionFailure,
    get,
)
from rath.backend.local import LocalBackend


def test_is_available_is_true() -> None:
    assert LocalBackend.is_available() is True


def test_capabilities_match_spec() -> None:
    cap = LocalBackend.capabilities()
    assert cap.isolation is IsolationLevel.PROCESS
    assert cap.supports_command is True
    assert cap.supports_filesystem is True
    assert cap.supports_code_interpreter is True
    assert cap.max_sandboxes is None


def test_supported_calls_covers_all_phase1_types() -> None:
    expected = {
        BackendToolCommandRun,
        BackendToolFilesRead,
        BackendToolFilesWrite,
        BackendToolFilesList,
        BackendToolFilesExists,
        BackendToolCodeRun,
    }
    assert LocalBackend.supported_calls() == expected


def test_local_is_registered_under_name_local() -> None:
    inst = get("local")
    assert isinstance(inst, LocalBackend)
    assert inst.name == "local"


def test_handle_is_a_real_working_directory() -> None:
    backend = get("local")
    sb = backend.open()
    try:
        assert os.path.isdir(sb.handle)
    finally:
        backend.close(sb)


def test_close_removes_working_directory() -> None:
    backend = get("local")
    sb = backend.open()
    handle = sb.handle
    backend.close(sb)
    assert not os.path.exists(handle)


def test_user_supplied_working_dir_honoured(tmp_path: object) -> None:
    backend = get("local")
    target = str(tmp_path)  # type: ignore[arg-type]
    sb = backend.open(BackendSandboxSpec(working_dir=target))
    try:
        assert sb.handle == target
    finally:
        backend.close(sb)
    assert os.path.isdir(target)


def test_close_does_not_remove_user_supplied_working_dir(tmp_path: object) -> None:
    """``close()`` must NOT rmtree a directory the caller supplied."""
    import pathlib

    target = pathlib.Path(str(tmp_path)) / "keep"  # type: ignore[arg-type]
    target.mkdir()
    sentinel = target / "important.txt"
    sentinel.write_text("do not delete me", encoding="utf-8")

    backend = get("local")
    sb = backend.open(BackendSandboxSpec(working_dir=str(target)))
    backend.close(sb)

    assert target.is_dir(), "user-supplied working_dir was removed by close()"
    assert sentinel.read_text(encoding="utf-8") == "do not delete me"


def test_command_missing_executable_returns_failure() -> None:
    backend = get("local")
    with backend.open() as sb:
        r = sb.dispatch(BackendToolCommandRun(cmd=["/nonexistent/rath_no_such_exe_xyz"]))
        assert isinstance(r, ToolExecutionFailure)
        assert r.kind in ("os_error", "unexpected")
