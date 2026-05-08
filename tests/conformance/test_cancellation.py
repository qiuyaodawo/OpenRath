"""After timing out a slow dispatch, the same sandbox still runs new commands."""

from __future__ import annotations

import pytest

from rath.backend import Backend, CommandResult, BackendToolCommandRun


def test_timeout_leaves_sandbox_usable(backend: Backend, python_cmd: list[str]) -> None:
    with backend.open() as sb:
        with pytest.raises(TimeoutError):
            sb.dispatch(
                BackendToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(10)",
                    ],
                    timeout=0.3,
                )
            )
        result = sb.dispatch(
            BackendToolCommandRun(cmd=[*python_cmd, "-c", "print('after')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"after" in result.stdout
