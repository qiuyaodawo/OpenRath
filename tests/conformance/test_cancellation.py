"""After timing out a slow dispatch, the same sandbox still runs new commands."""

from __future__ import annotations

from rath.backend import (
    Backend,
    BackendToolCommandRun,
    CommandResult,
    ToolExecutionFailure,
)


def test_timeout_leaves_sandbox_usable(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        r = sb.dispatch(
            BackendToolCommandRun(
                cmd=[
                    *python_cmd,
                    "-c",
                    "import time; time.sleep(10)",
                ],
                timeout=0.3,
            )
        )
        assert isinstance(r, ToolExecutionFailure)
        assert r.kind == "timeout"
        result = sb.dispatch(
            BackendToolCommandRun(cmd=[*python_cmd, "-c", "print('after')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"after" in result.stdout
