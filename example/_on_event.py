"""Shared streaming-delta callbacks for top-level examples.

These helpers provide the ``on_event=`` callback expected by
:func:`~rath.session.run_session_loop` and
:func:`~rath.session.run_session_compress`. Each helper returns a function
that writes streaming content to ``stdout`` as it is produced.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from rath.llm import RathLLMStreamDelta


def _print_delta(d: RathLLMStreamDelta) -> None:
    if d.content_delta:
        sys.stdout.write(d.content_delta)
        sys.stdout.flush()


def example_on_event() -> Callable[[RathLLMStreamDelta], None]:
    """Print each streamed delta's content to stdout (no trailing newline)."""

    return _print_delta


def optional_on_event(
    enabled: bool,
) -> Callable[[RathLLMStreamDelta], None] | None:
    """Same as :func:`example_on_event` when ``enabled``; otherwise ``None``."""

    return _print_delta if enabled else None
