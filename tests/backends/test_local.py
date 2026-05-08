"""Local-backend-only tests (always-on, temp working directories, close removes dir)."""

from __future__ import annotations

import os

import pytest

from rath.backend import (
    BackendSandboxSpec,
    BackendToolCodeRun,
    BackendToolCommandRun,
    BackendToolFilesExists,
    BackendToolFilesList,
    BackendToolFilesRead,
    BackendToolFilesWrite,
    IsolationLevel,
    UnsupportedBackendTool,
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


def test_unknown_code_language_raises_unsupported() -> None:
    backend = get("local")
    with backend.open() as sb:
        with pytest.raises(UnsupportedBackendTool):
            sb.dispatch(BackendToolCodeRun(code="puts 'hi'", language="ruby"))
