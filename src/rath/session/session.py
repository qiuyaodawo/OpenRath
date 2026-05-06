"""Session dataclass — chunk table plus optional sandbox binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from rath.backend import BackendSandbox
from rath.session.chunk import ChunkTable
from rath.session.graph import SessionLineage


@dataclass(slots=True)
class Session:
    """Conversation carrier (Torch ``Tensor`` analogy).

    Input sessions passed to ``run_session_loop`` are treated as immutable
    snapshots: the loop returns a **new** :class:`Session` that may share chunk
    tuples and rebinds the sandbox handle to the outgoing session.
    """

    chunk_table: ChunkTable
    id: UUID = field(default_factory=uuid4)
    sandbox: BackendSandbox | None = None
    lineage: SessionLineage | None = None

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
