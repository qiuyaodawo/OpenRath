"""Stream and :class:`Event` — threading-based FIFO dispatch bound to one sandbox."""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from types import TracebackType
from typing import Generic, TypeVar

from rath.backend.abc import BackendSandbox
from rath.backend.results import ToolResult
from rath.backend.tool_types import BackendTool

T = TypeVar("T")


class Future(Generic[T]):
    """Blocking handle to the result of a submitted tool call."""

    __slots__ = ("_evt", "_result", "_exc")

    def __init__(self) -> None:
        self._evt = threading.Event()
        self._result: T | None = None
        self._exc: BaseException | None = None

    def _set_result(self, result: T) -> None:
        self._result = result
        self._evt.set()

    def _set_exception(self, exc: BaseException) -> None:
        self._exc = exc
        self._evt.set()

    def result(self) -> T:
        self._evt.wait()
        if self._exc is not None:
            raise self._exc
        return self._result  # type: ignore[return-value]

    def done(self) -> bool:
        return self._evt.is_set()


class Event:
    """Synchronization marker that crosses :class:`Stream` boundaries."""

    __slots__ = ("_thread_evt", "_set_at")

    def __init__(self) -> None:
        self._thread_evt = threading.Event()
        self._set_at: float | None = None

    def _signal(self) -> None:
        self._set_at = time.perf_counter()
        self._thread_evt.set()

    def wait(self) -> None:
        self._thread_evt.wait()

    def query(self) -> bool:
        return self._thread_evt.is_set()

    def synchronize(self) -> None:
        self.wait()

    def elapsed_time(self, end: "Event") -> float:
        if self._set_at is None or end._set_at is None:
            raise RuntimeError(
                "elapsed_time requires both events to have been signaled"
            )
        return (end._set_at - self._set_at) * 1000.0


@dataclass(frozen=True, slots=True)
class _CallOp:
    call: BackendTool
    future: Future[ToolResult | bool]


@dataclass(frozen=True, slots=True)
class _RecordEventOp:
    event: Event


@dataclass(frozen=True, slots=True)
class _WaitEventOp:
    event: Event


@dataclass(frozen=True, slots=True)
class _SyncOp:
    evt: threading.Event


@dataclass(frozen=True, slots=True)
class _ShutdownOp:
    pass


_Op = _CallOp | _RecordEventOp | _WaitEventOp | _SyncOp | _ShutdownOp


class Stream:
    """Per-sandbox FIFO queue of tool-call operations (blocking worker thread)."""

    def __init__(self, sandbox: BackendSandbox, *, buffer: int = 0) -> None:
        self._sandbox = sandbox
        maxsize = 0 if buffer == 0 else buffer
        self._queue: queue.Queue[_Op | None] = queue.Queue(maxsize=maxsize)
        self._worker: threading.Thread | None = None
        self._busy = threading.Event()
        self._closed = False
        self._lock = threading.Lock()

    def __enter__(self) -> Stream:
        with self._lock:
            if self._closed:
                raise RuntimeError("stream is already closed")
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._queue.put(None)
        self._closed = True
        if self._worker is not None:
            self._worker.join(timeout=120.0)

    def submit(self, call: BackendTool) -> Future[ToolResult | bool]:
        future: Future[ToolResult | bool] = Future()
        self._queue.put(_CallOp(call=call, future=future))
        return future

    def synchronize(self) -> None:
        done = threading.Event()
        self._queue.put(_SyncOp(evt=done))
        done.wait()

    def query(self) -> bool:
        return self._queue.empty() and not self._busy.is_set()

    def record_event(self) -> Event:
        event = Event()
        self._queue.put(_RecordEventOp(event=event))
        return event

    def wait_event(self, event: Event) -> None:
        self._queue.put(_WaitEventOp(event=event))

    def wait_stream(self, other: Stream) -> None:
        evt = other.record_event()
        self.wait_event(evt)

    def _run(self) -> None:
        while True:
            op = self._queue.get()
            if op is None:
                break
            self._busy.set()
            try:
                self._handle(op)
            finally:
                self._busy.clear()

    def _handle(self, op: _Op) -> None:
        if isinstance(op, _CallOp):
            try:
                result = self._sandbox.dispatch(op.call)
            except Exception as exc:
                op.future._set_exception(exc)
            else:
                op.future._set_result(result)
        elif isinstance(op, _RecordEventOp):
            op.event._signal()
        elif isinstance(op, _WaitEventOp):
            op.event.wait()
        elif isinstance(op, _SyncOp):
            op.evt.set()
