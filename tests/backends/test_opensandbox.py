"""OpenSandboxBackend-specific tests.

Cross-backend behaviour is in ``tests/conformance/``. These tests cover
adapter-only concerns: capability shape, registration, ``is_available``
gating on environment, and that the SDK-fronted file-list / file-exists
paths return data shaped consistently with what conformance expects.

All tests in this file are gated on ``opensandbox_real``: they skip unless a
local ``opensandbox-server`` is reachable on ``localhost:8080``. There are no
mocks; the real server stands in for itself.
"""

from __future__ import annotations

import pytest

from rath.backend import (
    CodeResult,
    CommandResult,
    FileContent,
    FileEntries,
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
from rath.backend.adapters.opensandbox import OpenSandboxBackend
from tests.conftest import opensandbox_real

pytestmark = [pytest.mark.anyio, opensandbox_real, pytest.mark.opensandbox]


def test_capabilities_match_spec() -> None:
    cap = OpenSandboxBackend.capabilities()
    assert cap.isolation is IsolationLevel.CONTAINER
    assert cap.supports_command is True
    assert cap.supports_filesystem is True
    assert cap.supports_code_interpreter is True


def test_supported_calls_covers_all_phase1_types() -> None:
    expected = {
        FlowToolCommandRun,
        FlowToolFilesRead,
        FlowToolFilesWrite,
        FlowToolFilesList,
        FlowToolFilesExists,
        FlowToolCodeRun,
    }
    assert OpenSandboxBackend.supported_calls() == expected


def test_registered_under_name_opensandbox() -> None:
    inst = get("opensandbox")
    assert isinstance(inst, OpenSandboxBackend)
    assert inst.name == "opensandbox"


async def test_open_close_roundtrip() -> None:
    backend = get("opensandbox")
    sb = await backend.open()
    try:
        assert backend.sandbox_count() == 1
        assert sb.handle != ""
    finally:
        await backend.close(sb)
    assert backend.sandbox_count() == 0


async def test_command_run_stdin_raises_unsupported() -> None:
    """OpenSandbox's commands.run has no stdin; the adapter must surface that."""
    backend = get("opensandbox")
    async with await backend.open() as sb:
        with pytest.raises(UnsupportedFlowToolCall):
            await sb.dispatch(
                FlowToolCommandRun(cmd=["python3", "-c", "pass"], stdin=b"x")
            )


async def test_files_list_returns_entries_with_metadata() -> None:
    """Adapter's ``files.search`` -> ``FileEntries`` mapping must be well-formed."""
    backend = get("opensandbox")
    async with await backend.open() as sb:
        await sb.dispatch(FlowToolFilesWrite(path="/tmp/rath_a.txt", data="a"))
        await sb.dispatch(FlowToolFilesWrite(path="/tmp/rath_b.txt", data="b"))
        result = await sb.dispatch(FlowToolFilesList(path="/tmp"))
        assert isinstance(result, FileEntries)
        names = {e.name for e in result.entries}
        assert {"rath_a.txt", "rath_b.txt"}.issubset(names)


async def test_files_exists_true_and_false() -> None:
    backend = get("opensandbox")
    async with await backend.open() as sb:
        await sb.dispatch(FlowToolFilesWrite(path="/tmp/rath_present.txt", data="x"))
        assert (
            await sb.dispatch(FlowToolFilesExists(path="/tmp/rath_present.txt"))
            is True
        )
        assert (
            await sb.dispatch(
                FlowToolFilesExists(path="/tmp/rath_definitely_missing.txt")
            )
            is False
        )


async def test_unsupported_language_raises() -> None:
    backend = get("opensandbox")
    async with await backend.open() as sb:
        with pytest.raises(UnsupportedFlowToolCall):
            await sb.dispatch(FlowToolCodeRun(code="puts 'hi'", language="ruby"))


async def test_code_run_python_round_trip() -> None:
    """Smoke that ``codes.run`` produces both stdout and a result text."""
    backend = get("opensandbox")
    async with await backend.open() as sb:
        result = await sb.dispatch(
            FlowToolCodeRun(code="x = 1 + 1\nprint(x)\nx")
        )
        assert isinstance(result, CodeResult)
        assert result.error is None
        assert b"2" in result.stdout


async def test_files_read_text_and_bytes() -> None:
    backend = get("opensandbox")
    async with await backend.open() as sb:
        await sb.dispatch(FlowToolFilesWrite(path="/tmp/rath_rw.txt", data="hello"))
        text = await sb.dispatch(FlowToolFilesRead(path="/tmp/rath_rw.txt"))
        assert isinstance(text, FileContent)
        assert text.data == "hello"
        raw = await sb.dispatch(
            FlowToolFilesRead(path="/tmp/rath_rw.txt", encoding=None)
        )
        assert isinstance(raw, FileContent)
        assert raw.data == b"hello"


async def test_simple_command_run_exit_code_and_stdout() -> None:
    backend = get("opensandbox")
    async with await backend.open() as sb:
        result = await sb.dispatch(
            FlowToolCommandRun(cmd=["python3", "-c", "print('hello')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"hello" in result.stdout
