"""Factories that produce :data:`~rath.session.loop.ChunkAppendHook` callables.

The headline factory is :func:`persist_chunks`, which returns a hook that
mirrors every appended chunk to ``.openrath/sessions/<id>.jsonl`` as the
session loop runs. A second helper, :func:`compose_hooks`, chains multiple
hooks so a caller can write to disk AND print to stdout in one call::

    from rath.session.loop import sink_chunk_print, run_session_loop
    from rath.session.persistence import persist_chunks, compose_hooks

    hook = compose_hooks(persist_chunks(), sink_chunk_print())
    run_session_loop(user, agent, agent_provider=p, chunk_print=hook)
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import UUID

from rath.session.persistence.writer import SessionWriter

if TYPE_CHECKING:
    from rath.session.chunk import ChunkRow
    from rath.session.loop import ChunkAppendHook
    from rath.session.session import Session

__all__ = ["persist_chunks", "compose_hooks", "close_session_writers"]

logger = logging.getLogger(__name__)


def persist_chunks(
    *,
    sandbox_handle_id: str | None = None,
) -> ChunkAppendHook:
    """Return a :data:`ChunkAppendHook` that streams chunks to ``.openrath/sessions/<id>.jsonl``.

    One writer is created per ``session.id`` and reused across calls — so a
    long-running ``run_session_loop`` invocation appends to a single file.
    The header is written lazily on the first call so ``LineageRecorder``
    stamping (which happens inside ``run_session_loop`` after session
    construction) is captured. The trailer is written when the writer is
    closed; in the common loop case it is closed when the run completes
    (see :class:`_HookOwnedWriters` below).

    ``sandbox_handle_id`` is recorded verbatim in the header. Pass the UUID
    string returned by
    :meth:`~rath.backend.persistence.PersistentSandboxRegistry.alloc_local_id`
    so a future ``load_session(...).to_resumable_pair()`` can rebind the
    same sandbox workdir.
    """
    writers: dict[UUID, SessionWriter] = {}

    def _hook(row: "ChunkRow", index: int, session: "Session") -> object:
        writer = writers.get(session.id)
        if writer is None:
            writer = SessionWriter(session, sandbox_handle_id=sandbox_handle_id)
            writers[session.id] = writer
        # First call may carry an index > 0 because the loop seeds rows_list
        # with the user session's existing rows. Replay everything between
        # the writer's last position and the current index, then the row at
        # `index` itself.
        rows = session.chunk_table.rows
        already = writer.chunks_written
        # `index` is the position of `row` in `rows`; verify the loop
        # invariant before catching up earlier rows.
        if not (0 <= index < len(rows)) or rows[index] is not row:
            # Defensive: if the loop ever changes its invariants, fall back
            # to writing just the row we were given at the requested index.
            try:
                writer.write_chunk(index, row)
            except Exception:  # pragma: no cover -- defensive
                logger.exception("persist_chunks: failed to write chunk %d", index)
            return None
        for missing in range(already, index):
            writer.write_chunk(missing, rows[missing])
        writer.write_chunk(index, row)
        # Heuristic close: when the loop signals completion via the finish
        # row, the hook can't know that from here. Instead, callers should
        # use ``session.persistence.close_session_writers(hook)`` (see
        # below) or, more simply, rely on the trailer being written on
        # process exit via atexit. The writer's file is flushed after every
        # line so we are durable even without an explicit close.
        return None

    _hook._session_writers = writers  # type: ignore[attr-defined]
    return _hook


def compose_hooks(*hooks: "ChunkAppendHook") -> ChunkAppendHook:
    """Combine multiple hooks into one; each is invoked in order, errors propagate.

    Useful for "persist to disk AND print to console" — the canonical idiom::

        from rath.session.loop import sink_chunk_print
        compose_hooks(persist_chunks(), sink_chunk_print())

    When any input hook owns persisted-session writers (as returned by
    :func:`persist_chunks`), the composed hook exposes a merged
    ``_session_writers`` mapping so :func:`close_session_writers` continues
    to find and close them.
    """
    chain: tuple[ChunkAppendHook, ...] = tuple(hooks)

    def _composed(row: "ChunkRow", index: int, session: "Session") -> object:
        last: object = None
        for h in chain:
            last = h(row, index, session)
        return last

    merged: dict[UUID, SessionWriter] = {}
    has_writers = False
    for h in chain:
        owned = getattr(h, "_session_writers", None)
        if isinstance(owned, dict):
            has_writers = True
            merged.update(owned)
    if has_writers:
        # Live view — assignments into any child hook's dict won't reach
        # `merged`, but the typical loop pattern is "build hook, plug into
        # one run_session_loop, close at the end" so writers added during
        # the run come from the SAME persist_chunks instance. Re-aggregate
        # at close time by walking the chain once more.
        def _aggregate() -> dict[UUID, SessionWriter]:
            agg: dict[UUID, SessionWriter] = {}
            for h2 in chain:
                owned2 = getattr(h2, "_session_writers", None)
                if isinstance(owned2, dict):
                    agg.update(owned2)
            return agg

        _composed._session_writers_view = _aggregate  # type: ignore[attr-defined]
        _composed._session_writers = merged  # type: ignore[attr-defined]
    return _composed


def close_session_writers(hook: "ChunkAppendHook") -> Iterable[UUID]:
    """Write trailers for every session writer owned by ``hook``.

    ``persist_chunks()`` returns a hook with a private ``_session_writers``
    attribute; :func:`compose_hooks` aggregates them when wrapping multiple
    hooks. This helper iterates that mapping, calls ``close()`` on each
    writer (writing the trailer), and returns the closed session ids. Safe
    to call multiple times; closed writers are idempotent.

    Use this when you want a graceful trailer instead of leaving sessions
    in the ``closed=False`` state that a crashed-mid-run would produce.
    """
    # Prefer the live aggregator on composed hooks, fall back to the static
    # mapping on a plain persist_chunks() hook.
    view = getattr(hook, "_session_writers_view", None)
    if callable(view):
        writers: dict[UUID, SessionWriter] | None = view()
    else:
        writers = getattr(hook, "_session_writers", None)
    if writers is None:
        return ()
    closed: list[UUID] = []
    for sid, writer in writers.items():
        try:
            writer.close()
            closed.append(sid)
        except Exception:  # pragma: no cover -- defensive
            logger.exception("failed to close persisted writer for session %s", sid)
    return tuple(closed)
