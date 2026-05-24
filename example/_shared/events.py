"""Streaming-delta callbacks shared by the examples."""

from __future__ import annotations

import sys
from collections.abc import Callable

from rath.llm import RathLLMStreamDelta

OnEvent = Callable[[RathLLMStreamDelta], None]


def _print_delta(delta: RathLLMStreamDelta) -> None:
    if delta.content_delta:
        sys.stdout.write(delta.content_delta)
        sys.stdout.flush()


def stream_to_stdout() -> OnEvent:
    """Return an ``on_event`` callback that prints streamed content to stdout.

    Pass this as ``on_event=`` to :class:`flow.Agent` or ``run_session_loop``
    to watch tokens arrive live. It writes no trailing newline, so the caller
    is responsible for a final ``print()`` after the loop returns.
    """
    return _print_delta
