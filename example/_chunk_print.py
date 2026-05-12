"""Shared chunk-append hooks for top-level examples (one line per new row)."""

from __future__ import annotations

from rath.session import ChunkAppendHook, sink_chunk_print


def example_chunk_print() -> ChunkAppendHook:
    """Print each newly appended loop / compress row as one brief line."""

    return sink_chunk_print(print)


def optional_chunk_print(enabled: bool) -> ChunkAppendHook | None:
    """When ``enabled``, same as :func:`example_chunk_print`; otherwise ``None``."""

    return sink_chunk_print(print) if enabled else None
