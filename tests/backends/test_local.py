"""LocalBackend-specific tests.

Cross-backend behaviour is in ``tests/conformance/``; this file covers things
unique to the local backend: that it is always available, its capabilities
match the design spec, the sandbox handle is a real on-disk working directory,
and that close() removes the working directory.
"""

from __future__ import annotations

import os

import pytest

from rath.backend import (
    BackendSandboxSpec,
    FlowToolCodeRun,
    FlowToolCommandRun,
    FlowToolFilesExists,
    FlowToolFilesList,
    FlowToolFilesRead,
    FlowToolFilesWrite,
    IsolationLevel,
    UnsupportedFlowToolCall,
    get,
)
from rath.backend.adapters.local import LocalBackend

pytestmark = pytest.mark.anyio


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
        FlowToolCommandRun,
        FlowToolFilesRead,
        FlowToolFilesWrite,
        FlowToolFilesList,
        FlowToolFilesExists,
        FlowToolCodeRun,
    }
    assert LocalBackend.supported_calls() == expected


def test_local_is_registered_under_name_local() -> None:
    inst = get("local")
    assert isinstance(inst, LocalBackend)
    assert inst.name == "local"


async def test_handle_is_a_real_working_directory() -> None:
    backend = get("local")
    sb = await backend.open()
    try:
        assert os.path.isdir(sb.handle)
    finally:
        await backend.close(sb)


async def test_close_removes_working_directory() -> None:
    backend = get("local")
    sb = await backend.open()
    handle = sb.handle
    await backend.close(sb)
    assert not os.path.exists(handle)


async def test_user_supplied_working_dir_honoured(tmp_path: object) -> None:
    backend = get("local")
    target = str(tmp_path)  # type: ignore[arg-type]
    sb = await backend.open(BackendSandboxSpec(working_dir=target))
    try:
        assert sb.handle == target
    finally:
        await backend.close(sb)


async def test_unknown_code_language_raises_unsupported() -> None:
    backend = get("local")
    async with await backend.open() as sb:
        with pytest.raises(UnsupportedFlowToolCall):
            await sb.dispatch(FlowToolCodeRun(code="puts 'hi'", language="ruby"))
