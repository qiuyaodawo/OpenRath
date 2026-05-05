"""Conformance: cancellation of in-flight dispatches.

Cancelling a slow dispatch must not corrupt the sandbox; subsequent dispatches
on the same handle should still succeed.
"""

from __future__ import annotations

import anyio
import pytest

from rath.backend import Backend, CommandResult, FlowToolCommandRun

pytestmark = pytest.mark.anyio


async def test_cancellation_leaves_sandbox_usable(
    backend: Backend, python_cmd: list[str]
) -> None:
    async with await backend.open() as sb:
        with anyio.move_on_after(0.3):
            await sb.dispatch(
                FlowToolCommandRun(
                    cmd=[
                        *python_cmd,
                        "-c",
                        "import time; time.sleep(10)",
                    ]
                )
            )
        # The cancel scope exited normally; the sandbox must still be usable.
        result = await sb.dispatch(
            FlowToolCommandRun(cmd=[*python_cmd, "-c", "print('after')"])
        )
        assert isinstance(result, CommandResult)
        assert result.exit_code == 0
        assert b"after" in result.stdout
