"""Stream and Event default implementation, anyio-based.

A :class:`Stream` is a FIFO queue of operations bound to a single
:class:`Sandbox`. A worker task pulls operations off the queue and dispatches
them through the owning backend, in submission order. Multiple streams over
the same sandbox run their queues in parallel.

The implementation is intentionally backend-agnostic: any backend whose
``dispatch`` method is correctly async benefits from streams without having
to opt in. A backend can still subclass :class:`Stream` later if it has a
native parallel-dispatch primitive worth exposing.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from types import TracebackType
from typing import TYPE_CHECKING, Generic, TypeVar

import anyio

from rath.backend._calls import ToolCall
from rath.backend._results import ToolResult

if TYPE_CHECKING:
    from collections.abc import Generator

    from rath.backend._abc import Sandbox


T = TypeVar("T")


class Future(Generic[T]):
    """Awaitable handle to the result of a submitted :class:`ToolCall`.

    Awaiting the future blocks until the worker has dispatched the call. If
    dispatch raised, awaiting re-raises the same exception.
    """

    __slots__ = ("_event", "_result", "_exc")

    def __init__(self) -> None:
        self._event: anyio.Event = anyio.Event()
        self._result: T | None = None
        self._exc: BaseException | None = None

    def _set_result(self, result: T) -> None:
        self._result = result
        self._event.set()

    def _set_exception(self, exc: BaseException) -> None:
        self._exc = exc
        self._event.set()

    async def wait(self) -> T:
        await self._event.wait()
        if self._exc is not None:
            raise self._exc
        # Post-condition: when _event is set and _exc is None, _result is
        # populated; this is enforced by _set_result / _set_exception.
        return self._result  # type: ignore[return-value]

    def __await__(self) -> Generator[object, None, T]:
        return self.wait().__await__()

    def done(self) -> bool:
        return self._event.is_set()


class Event:
    """Synchronization marker that crosses :class:`Stream` boundaries.

    An event records a logical point in a stream's submission timeline.
    Other streams can wait on an event so their next submission only runs
    after the recording stream has passed that point.
    """

    __slots__ = ("_anyio_event", "_set_at")

    def __init__(self) -> None:
        self._anyio_event: anyio.Event = anyio.Event()
        self._set_at: float | None = None

    def _signal(self) -> None:
        self._set_at = time.perf_counter()
        self._anyio_event.set()

    async def wait(self) -> None:
        await self._anyio_event.wait()

    def query(self) -> bool:
        return self._anyio_event.is_set()

    async def synchronize(self) -> None:
        await self.wait()

    def elapsed_time(self, end: "Event") -> float:
        """Return milliseconds elapsed between this event and ``end``.

        Both events must have fired before this is called.
        """
        if self._set_at is None or end._set_at is None:
            raise RuntimeError(
                "elapsed_time requires both events to have been signaled"
            )
        return (end._set_at - self._set_at) * 1000.0


# --------------------------------------------------------------------- ops


@dataclass(frozen=True, slots=True)
class _CallOp:
    call: ToolCall
    future: Future[ToolResult | bool]


@dataclass(frozen=True, slots=True)
class _RecordEventOp:
    event: Event


@dataclass(frozen=True, slots=True)
class _WaitEventOp:
    event: Event


@dataclass(frozen=True, slots=True)
class _SyncOp:
    done: anyio.Event


_Op = _CallOp | _RecordEventOp | _WaitEventOp | _SyncOp


# ------------------------------------------------------------------- stream


class Stream:
    """Per-sandbox FIFO queue of tool-call operations.

    A stream is itself an async context manager. The worker task that drains
    its queue lives inside that context; on exit the stream stops accepting
    new submissions and awaits in-flight work.

    ``buffer=0`` (the default) means an unbounded queue. Set ``buffer`` to a
    positive integer to apply backpressure: :meth:`submit` will await when
    the queue is full.
    """

    def __init__(self, sandbox: "Sandbox", *, buffer: int = 0) -> None:
        self._sandbox = sandbox
        # anyio rejects non-inf floats for ``max_buffer_size``; pass the int
        # directly when bounded.
        size: int | float = math.inf if buffer == 0 else buffer
        send, recv = anyio.create_memory_object_stream[_Op](max_buffer_size=size)
        self._send = send
        self._recv = recv
        self._task_group: anyio.abc.TaskGroup | None = None
        self._busy: bool = False
        self._closed: bool = False

    async def __aenter__(self) -> "Stream":
        if self._closed:
            raise RuntimeError("stream is already closed")
        self._task_group = anyio.create_task_group()
        await self._task_group.__aenter__()
        self._task_group.start_soon(self._run)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Closing the send side signals end-of-stream to the worker, which
        # then drains and exits cleanly.
        await self._send.aclose()
        self._closed = True
        assert self._task_group is not None
        await self._task_group.__aexit__(exc_type, exc, tb)

    async def submit(self, call: ToolCall) -> Future[ToolResult | bool]:
        future: Future[ToolResult | bool] = Future()
        await self._send.send(_CallOp(call=call, future=future))
        return future

    async def synchronize(self) -> None:
        done = anyio.Event()
        await self._send.send(_SyncOp(done=done))
        await done.wait()

    async def query(self) -> bool:
        """Return ``True`` iff the queue is empty and the worker is idle."""
        return (
            self._send.statistics().current_buffer_used == 0 and not self._busy
        )

    async def record_event(self) -> Event:
        event = Event()
        await self._send.send(_RecordEventOp(event=event))
        return event

    async def wait_event(self, event: Event) -> None:
        await self._send.send(_WaitEventOp(event=event))

    async def wait_stream(self, other: "Stream") -> None:
        e = await other.record_event()
        await self.wait_event(e)

    async def _run(self) -> None:
        async with self._recv:
            async for op in self._recv:
                self._busy = True
                try:
                    await self._handle(op)
                finally:
                    self._busy = False

    async def _handle(self, op: _Op) -> None:
        if isinstance(op, _CallOp):
            try:
                result = await self._sandbox.dispatch(op.call)
            except Exception as exc:
                op.future._set_exception(exc)
            else:
                op.future._set_result(result)
        elif isinstance(op, _RecordEventOp):
            op.event._signal()
        elif isinstance(op, _WaitEventOp):
            await op.event.wait()
        elif isinstance(op, _SyncOp):
            op.done.set()
