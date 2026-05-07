"""Session dataclass — chunk table plus optional sandbox binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from rath.backend import BackendSandbox
from rath.session.chunk import ChunkTable
from rath.session.graph.kind import LineageKind
from rath.session.graph.legacy import SessionLineage


@dataclass(slots=True)
class Session:
    """Chunk transcript (:attr:`chunk_table`), optional sandbox, and lineage metadata.

    :func:`~rath.session.loop.run_session_loop` takes the sandbox attached to an
    incoming user session and rebinds it to the returned session.

    Flat lineage (preferred graph substrate): :attr:`parent_session_ids` (ordered
    parents), :attr:`lineage_operator`, :attr:`lineage_kind`, :attr:`lineage_extras`.
    :attr:`lineage` is an optional legacy DTO tying loop outputs to producer sessions.
    Writes to lineage fields honour :func:`~rath.session.graph.session_graph_mode`;
    primitives and ``run_session_loop`` are the intended mutation sites.
    """

    chunk_table: ChunkTable
    id: UUID = field(default_factory=uuid4)
    sandbox: BackendSandbox | None = None
    lineage: SessionLineage | None = None
    parent_session_ids: tuple[UUID, ...] = ()
    lineage_operator: str = "implicit"
    lineage_kind: LineageKind = LineageKind.UNKNOWN
    lineage_extras: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_system_prompt(cls, prompt: str) -> Session:
        from rath.session.chunk import system_text_chunk

        return cls(chunk_table=ChunkTable(rows=(system_text_chunk(prompt),)))

    @classmethod
    def user_message(cls, text: str) -> Session:
        from rath.session.chunk import user_text_chunk

        return cls(chunk_table=ChunkTable(rows=(user_text_chunk(text),)))

    def with_sandbox(self, sandbox: BackendSandbox) -> Session:
        self.sandbox = sandbox
        return self

    def require_sandbox(self) -> BackendSandbox:
        if self.sandbox is None or self.sandbox.closed:
            raise RuntimeError("session has no active sandbox")
        return self.sandbox

    def take_sandbox(self) -> BackendSandbox:
        """Detach sandbox for rebinding to another session."""
        if self.sandbox is None:
            raise RuntimeError("no sandbox to take")
        sb = self.sandbox
        self.sandbox = None
        return sb

    def bind_sandbox(self, sandbox: BackendSandbox) -> Session:
        """Attach sandbox to this session (active executor)."""
        self.sandbox = sandbox
        return self
