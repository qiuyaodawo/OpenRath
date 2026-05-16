"""Append-only writer for one persisted session file.

A :class:`SessionWriter` owns the file handle for ``<sessions>/<id>.jsonl``
during the lifetime of one session. The header is written lazily on the
first :meth:`write_chunk` call (so the writer can capture lineage stamping
that the session loop applies after construction). Each subsequent chunk is
serialized as one line, ``json.dumps(..., ensure_ascii=False)`` + ``"\\n"``,
followed by ``flush()`` so a ``kill -9`` loses at most the last partial line.

``close()`` writes a ``record_type=trailer`` line carrying the final chunk
count and cumulative usage. A missing trailer is the durable signal that
the writing process crashed mid-session — the loader surfaces it as
``PersistedSession.closed = False``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import TracebackType
from typing import IO, Any

from rath.config.secrets import chmod_user_only
from rath.session.chunk import ChunkRow
from rath.session.persistence._lock import FileLock
from rath.session.persistence._serialize import (
    build_chunk_record,
    build_header,
    build_trailer,
)
from rath.session.persistence.paths import ensure_sessions_dir, session_file
from rath.session.session import Session

__all__ = ["SessionWriter"]

logger = logging.getLogger(__name__)


class SessionWriter:
    """Append-only JSONL writer for one :class:`~rath.session.session.Session`.

    Usage::

        writer = SessionWriter(session)
        writer.write_chunk(0, row_0)        # opens file, writes header + chunk 0
        writer.write_chunk(1, row_1)
        ...
        writer.close()                       # writes trailer

    The writer can also be used as a context manager — ``__exit__`` calls
    :meth:`close` when no exception is in flight and :meth:`abandon`
    otherwise (so a crash midway leaves the file trailer-less, marking the
    session as ``closed=False`` on reload).
    """

    __slots__ = (
        "_session",
        "_path",
        "_sandbox_handle_id",
        "_file",
        "_lock",
        "_chunks_written",
        "_header_written",
        "_closed",
    )

    def __init__(
        self,
        session: Session,
        *,
        sandbox_handle_id: str | None = None,
        path: Path | None = None,
    ) -> None:
        self._session = session
        self._path = (path or session_file(session.id)).resolve()
        self._sandbox_handle_id = sandbox_handle_id
        self._file: IO[str] | None = None
        self._lock: FileLock | None = None
        self._chunks_written = 0
        self._header_written = False
        self._closed = False

    @property
    def path(self) -> Path:
        """Absolute path to the on-disk JSONL file."""
        return self._path

    @property
    def chunks_written(self) -> int:
        """Number of ``record_type=chunk`` lines flushed so far."""
        return self._chunks_written

    # ------------------------------------------------------------------ writes

    def write_chunk(self, index: int, row: ChunkRow) -> None:
        """Append one chunk record. Writes the header lazily on first call."""
        if self._closed:
            raise RuntimeError(
                f"SessionWriter({self._path}) is closed; cannot append more chunks",
            )
        self._open_if_needed()
        if not self._header_written:
            self._write_record(
                build_header(self._session, sandbox_handle_id=self._sandbox_handle_id)
            )
            self._header_written = True
        self._write_record(build_chunk_record(index, row))
        self._chunks_written += 1

    def close(self) -> None:
        """Write the trailer (graceful close) and release the file handle.

        Idempotent. Safe to call from ``__exit__`` after :meth:`write_chunk`
        even when no chunks were written — in that case no header / trailer
        is emitted and the on-disk file is left untouched.
        """
        if self._closed:
            return
        try:
            if self._header_written and self._file is not None:
                self._write_record(
                    build_trailer(
                        self._session,
                        final_chunk_count=self._chunks_written,
                    )
                )
        finally:
            self._release()
            self._closed = True

    def abandon(self) -> None:
        """Release the file handle WITHOUT writing a trailer.

        Marks the session as ``closed=False`` on reload — the same state as
        if the process had been ``kill -9``'d. Useful when the loop bails out
        on an exception and the persistence layer wants to preserve that
        signal explicitly.
        """
        if self._closed:
            return
        self._release()
        self._closed = True

    # ------------------------------------------------------------------ context

    def __enter__(self) -> "SessionWriter":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abandon()

    # ------------------------------------------------------------------ internals

    def _open_if_needed(self) -> None:
        if self._file is not None:
            return
        # Ensure the parent directory exists. For the default path this is
        # ``<resolved>/sessions``; for callers that passed an explicit path
        # we still want to ``mkdir -p`` so unit tests / one-off uses don't
        # need to pre-create the directory.
        self._path.parent.mkdir(parents=True, exist_ok=True)
        ensure_sessions_dir()
        existed = self._path.exists()
        self._file = self._path.open("a", encoding="utf-8")
        # Acquire an exclusive advisory lock so a second process opening the
        # same session id fails fast instead of silently interleaving lines.
        self._lock = FileLock(self._file)
        try:
            self._lock.acquire()
        except Exception:
            self._file.close()
            self._file = None
            self._lock = None
            raise
        # Apply 0600 the first time we touch the file. Idempotent on POSIX;
        # no-op on Windows (NTFS uses ACLs).
        if not existed:
            chmod_user_only(self._path)

    def _write_record(self, record: dict[str, Any]) -> None:
        assert self._file is not None
        line = json.dumps(record, ensure_ascii=False, sort_keys=False)
        self._file.write(line + "\n")
        self._file.flush()

    def _release(self) -> None:
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        if self._file is None:
            return
        try:
            self._file.close()
        except OSError:  # pragma: no cover -- racing fs
            logger.exception("failed to close persisted session file %s", self._path)
        self._file = None
