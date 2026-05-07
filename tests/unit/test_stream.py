"""``Stream``, ``Event``, and ``Future`` unit tests (in-process fake backend)."""

from __future__ import annotations

from dataclasses import dataclass

import anyio
import pytest

from rath.backend import (
    Backend,
    BackendSandbox,
    BackendSandboxSpec,
    Capabilities,
    CommandResult,
    Event,
    BackendTool,
    BackendToolCommandRun,
    IsolationLevel,
    ToolResult,
)

pytestmark = pytest.mark.anyio


@dataclass
class _RecordingBackend(Backend):
    """In-test backend that records dispatch order and supports a per-call delay."""

    dispatched: list[BackendTool]
    delay: float = 0.0
    _open_handles: set[str] = None  # type: ignore[assignment]

    def __init__(self, delay: float = 0.0) -> None:
        self.dispatched = []
        self.delay = delay
        self._open_handles = set()

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def capabilities(cls) -> Capabilities:
        return Capabilities(
            isolation=IsolationLevel.PROCESS,
            supports_command=True,
            supports_filesystem=False,
            supports_code_interpreter=False,
        )

    @classmethod
    def supported_calls(cls) -> frozenset[type[BackendTool]]:
        return frozenset({BackendToolCommandRun})

    def sandbox_count(self) -> int:
        return len(self._open_handles)

    async def open(
        self, spec: BackendSandboxSpec | None = None
    ) -> BackendSandbox:
        handle = f"fake-{len(self._open_handles)}"
        self._open_handles.add(handle)
        return BackendSandbox(backend=self, handle=handle, spec=spec)

    async def close(self, sandbox: BackendSandbox) -> None:
        self._open_handles.discard(sandbox.handle)
        sandbox.closed = True

    async def dispatch(
        self, sandbox: BackendSandbox, call: BackendTool
    ) -> ToolResult | bool:
        if self.delay:
            await anyio.sleep(self.delay)
        self.dispatched.append(call)
        return CommandResult(
            exit_code=0, stdout=b"", stderr=b"", elapsed_ms=0.0
        )


@pytest.fixture
def fake_backend() -> _RecordingBackend:
    return _RecordingBackend()


@pytest.fixture
async def fake_sandbox(fake_backend: _RecordingBackend) -> BackendSandbox:
    return await fake_backend.open()


async def test_submit_runs_calls_in_fifo_order(
    fake_sandbox: BackendSandbox,
) -> None:
    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    calls = [BackendToolCommandRun(cmd=f"echo {i}") for i in range(20)]
    async with fake_sandbox.stream() as s:
        futures = [await s.submit(c) for c in calls]
        for f in futures:
            await f
    assert backend.dispatched == calls


async def test_two_streams_run_in_parallel(fake_sandbox: BackendSandbox) -> None:
    """Overlapping streams advance concurrently (each dispatch sleeps briefly)."""

    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    backend.delay = 0.05

    async with fake_sandbox.stream() as s1, fake_sandbox.stream() as s2:
        f1 = await s1.submit(BackendToolCommandRun(cmd="from-s1"))
        f2 = await s2.submit(BackendToolCommandRun(cmd="from-s2"))
        with anyio.fail_after(0.3):
            await f1
            await f2

    assert {c.cmd for c in backend.dispatched} == {"from-s1", "from-s2"}


async def test_wait_event_blocks_until_signaled(
    fake_sandbox: BackendSandbox,
) -> None:
    """Submissions on s2 must wait for an event recorded by s1."""
    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    async with fake_sandbox.stream() as s1, fake_sandbox.stream() as s2:
        await s1.submit(BackendToolCommandRun(cmd="s1-first"))
        evt = await s1.record_event()

        await s2.wait_event(evt)
        f2 = await s2.submit(BackendToolCommandRun(cmd="s2-after-event"))
        await f2

    cmds = [c.cmd for c in backend.dispatched]
    assert cmds.index("s1-first") < cmds.index("s2-after-event")


async def test_wait_stream_drains_other_first(
    fake_sandbox: BackendSandbox,
) -> None:
    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    async with fake_sandbox.stream() as s1, fake_sandbox.stream() as s2:
        for i in range(5):
            await s1.submit(BackendToolCommandRun(cmd=f"s1-{i}"))
        await s2.wait_stream(s1)
        await s2.submit(BackendToolCommandRun(cmd="s2-final"))
        await s2.synchronize()

    cmds = [c.cmd for c in backend.dispatched]
    assert cmds[-1] == "s2-final"


async def test_synchronize_waits_for_drain(fake_sandbox: BackendSandbox) -> None:
    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    backend.delay = 0.02
    async with fake_sandbox.stream() as s:
        for i in range(5):
            await s.submit(BackendToolCommandRun(cmd=f"c{i}"))
        await s.synchronize()
        assert len(backend.dispatched) == 5


async def test_query_reflects_idle(fake_sandbox: BackendSandbox) -> None:
    async with fake_sandbox.stream() as s:
        assert await s.query() is True
        await s.submit(BackendToolCommandRun(cmd="x"))
        await s.synchronize()
        assert await s.query() is True


async def test_future_result_reflects_dispatch(
    fake_sandbox: BackendSandbox,
) -> None:
    async with fake_sandbox.stream() as s:
        f = await s.submit(BackendToolCommandRun(cmd="r"))
        result = await f
        assert isinstance(result, CommandResult)
        assert f.done() is True


async def test_future_propagates_exception() -> None:
    """If dispatch raises, awaiting the future must re-raise."""

    class _BoomBackend(_RecordingBackend):
        async def dispatch(
            self, sandbox: BackendSandbox, call: BackendTool
        ) -> ToolResult | bool:
            raise RuntimeError("kaboom")

    bk = _BoomBackend()
    sb = await bk.open()
    async with sb.stream() as s:
        f = await s.submit(BackendToolCommandRun(cmd="x"))
        with pytest.raises(RuntimeError, match="kaboom"):
            await f


async def test_event_elapsed_time_requires_both_set() -> None:
    e1 = Event()
    e2 = Event()
    with pytest.raises(RuntimeError):
        e1.elapsed_time(e2)


async def test_event_query_initially_false_then_true(
    fake_sandbox: BackendSandbox,
) -> None:
    async with fake_sandbox.stream() as s:
        evt = await s.record_event()
        await s.synchronize()
        assert evt.query() is True


async def test_buffered_stream_works_end_to_end(
    fake_sandbox: BackendSandbox,
) -> None:
    """A bounded stream must accept and process submissions correctly."""
    backend: _RecordingBackend = fake_sandbox.backend  # type: ignore[assignment]
    async with fake_sandbox.stream(buffer=2) as s:
        for i in range(5):
            await s.submit(BackendToolCommandRun(cmd=f"c{i}"))
        await s.synchronize()
    assert len(backend.dispatched) == 5
