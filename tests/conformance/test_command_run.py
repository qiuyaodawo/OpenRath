"""Conformance: CommandRun semantics across all backends."""

from __future__ import annotations

import sys

import pytest

from rath.backend import Backend, CommandResult, CommandRun, FilesWrite

pytestmark = pytest.mark.anyio


async def test_basic_stdout(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(
            CommandRun(cmd=[sys.executable, "-c", "print('hello')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"hello" in result.stdout
        assert result.elapsed_ms >= 0


async def test_nonzero_exit_code(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(
            CommandRun(cmd=[sys.executable, "-c", "import sys; sys.exit(7)"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 7


async def test_stderr_capture(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(
            CommandRun(
                cmd=[sys.executable, "-c", "import sys; sys.stderr.write('boom')"]
            )
        )
        assert isinstance(result, CommandResult)
        assert b"boom" in result.stderr


async def test_env_passthrough(backend: Backend) -> None:
    async with await backend.open() as sb:
        result = await sb.dispatch(
            CommandRun(
                cmd=[
                    sys.executable,
                    "-c",
                    "import os; print(os.environ['RATH_VAR'])",
                ],
                env={"RATH_VAR": "hello42"},
            )
        )
        assert isinstance(result, CommandResult)
        assert b"hello42" in result.stdout


async def test_stdin_input(backend: Backend) -> None:
    if backend.name == "opensandbox":
        pytest.skip("OpenSandbox commands.run has no stdin parameter")
    async with await backend.open() as sb:
        result = await sb.dispatch(
            CommandRun(
                cmd=[
                    sys.executable,
                    "-c",
                    "import sys; sys.stdout.write(sys.stdin.read().upper())",
                ],
                stdin=b"abc",
            )
        )
        assert isinstance(result, CommandResult)
        assert b"ABC" in result.stdout


async def test_default_cwd_is_sandbox_root(backend: Backend) -> None:
    """A relative path written via FilesWrite must be readable by a command
    that defaults to the sandbox cwd."""
    async with await backend.open() as sb:
        await sb.dispatch(FilesWrite(path="marker.txt", data="found"))
        result = await sb.dispatch(
            CommandRun(
                cmd=[
                    sys.executable,
                    "-c",
                    "print(open('marker.txt').read())",
                ]
            )
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"found" in result.stdout


async def test_timeout_raises_timeout_error(backend: Backend) -> None:
    async with await backend.open() as sb:
        with pytest.raises(TimeoutError):
            await sb.dispatch(
                CommandRun(
                    cmd=[
                        sys.executable,
                        "-c",
                        "import time; time.sleep(5)",
                    ],
                    timeout=0.5,
                )
            )
