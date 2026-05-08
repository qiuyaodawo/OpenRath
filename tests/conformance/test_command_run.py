"""``BackendToolCommandRun`` stdout/stderr/exit code per backend."""

from __future__ import annotations

import pytest

from rath.backend import (
    Backend,
    CommandResult,
    BackendToolCommandRun,
    BackendToolFilesWrite,
)


def test_basic_stdout(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        result = sb.dispatch(
            BackendToolCommandRun(cmd=[*python_cmd, "-c", "print('hello')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"hello" in result.stdout
        assert result.elapsed_ms >= 0


def test_nonzero_exit_code(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        result = sb.dispatch(
            BackendToolCommandRun(
                cmd=[*python_cmd, "-c", "import sys; sys.exit(7)"]
            )
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 7


def test_stderr_capture(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        result = sb.dispatch(
            BackendToolCommandRun(
                cmd=[*python_cmd, "-c", "import sys; sys.stderr.write('boom')"]
            )
        )
        assert isinstance(result, CommandResult)
        assert b"boom" in result.stderr


def test_env_passthrough(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        result = sb.dispatch(
            BackendToolCommandRun(
                cmd=[
                    *python_cmd,
                    "-c",
                    "import os; print(os.environ['RATH_VAR'])",
                ],
                env={"RATH_VAR": "hello42"},
            )
        )
        assert isinstance(result, CommandResult)
        assert b"hello42" in result.stdout


def test_stdin_input(backend: Backend, python_cmd: list[str]) -> None:
    if backend.name == "opensandbox":
        pytest.skip("OpenSandbox commands.run has no stdin parameter")
    with backend.open() as sb:
        result = sb.dispatch(
            BackendToolCommandRun(
                cmd=[
                    *python_cmd,
                    "-c",
                    "import sys; sys.stdout.write(sys.stdin.read().upper())",
                ],
                stdin=b"abc",
            )
        )
        assert isinstance(result, CommandResult)
        assert b"ABC" in result.stdout


def test_default_cwd_is_sandbox_root(backend: Backend, python_cmd: list[str]) -> None:
    """A relative path written via BackendToolFilesWrite must be readable by a
    command that defaults to the sandbox cwd."""
    with backend.open() as sb:
        sb.dispatch(BackendToolFilesWrite(path="marker.txt", data="found"))
        result = sb.dispatch(
            BackendToolCommandRun(
                cmd=[
                    *python_cmd,
                    "-c",
                    "print(open('marker.txt').read())",
                ]
            )
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"found" in result.stdout


def test_timeout_raises_timeout_error(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        with pytest.raises(TimeoutError):
            sb.dispatch(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(5)",
                    ],
                    timeout=0.5,
                )
            )
