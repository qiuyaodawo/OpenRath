"""Session dataclass — chunk table plus optional sandbox binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import TracebackType
from typing import Any
from uuid import UUID, uuid4

from rath.backend import BackendSandbox, BackendSandboxSpec, get
from rath.llm import add_usage
from rath.llm.chat_response import RathLLMTokenUsage
from rath.session.chunk import ChunkKind, ChunkRow, ChunkTable
from rath.session.graph.kind import LineageKind
from rath.session.graph.legacy import SessionLineage
from rath.session.graph.recording import LineageRecorder


def _coerce_sandbox_open_spec(
    spec: BackendSandboxSpec | str | None,
) -> BackendSandboxSpec | None:
    """Accept :class:`~rath.backend.abc.BackendSandboxSpec` or a ``working_dir`` path string."""

    if spec is None:
        return None
    if isinstance(spec, str):
        return BackendSandboxSpec(working_dir=spec)
    return spec


# Defaults for chunk previews in :meth:`Session.__str__` and ``__repr__``.
_SESSION_REPR_CHUNK_EDGE = 4
_SESSION_REPR_TEXT_MAX = 256
_SESSION_REPR_TOOL_ARGS_MAX = 160


def _preview_text(s: str, *, max_chars: int = _SESSION_REPR_TEXT_MAX) -> str:
    """Flatten newlines and truncate long strings with a centered `` ... `` gap."""

    if not s:
        return ""
    t = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    if max_chars <= 8 or len(t) <= max_chars:
        return t
    edge = max(1, (max_chars - 5) // 2)
    return f"{t[:edge]} ... {t[-edge:]}"


def _format_chunk_row(index: int, row: ChunkRow) -> str:
    kind = row.kind
    p = row.payload
    if kind in (ChunkKind.SYSTEM, ChunkKind.USER):
        body = _preview_text(str(p.get("content", "")))
        return f"[{index}] {kind.value}: {body!r}"
    if kind == ChunkKind.ASSISTANT:
        parts: list[str] = []
        c = p.get("content")
        if c is not None and str(c).strip():
            parts.append(f"text={_preview_text(str(c))!r}")
        tc_raw = p.get("tool_calls") or []
        if tc_raw:
            names: list[str] = []
            for d in tc_raw:
                fn = d.get("function") or {}
                nm = str(fn.get("name", "?"))
                args = _preview_text(
                    str(fn.get("arguments", "")), max_chars=_SESSION_REPR_TOOL_ARGS_MAX
                )
                names.append(f"{nm}({args!r})")
            parts.append(f"tools=[{', '.join(names)}]")
        summary = ", ".join(parts) if parts else "(empty)"
        return f"[{index}] {kind.value}: {summary}"
    if kind == ChunkKind.TOOL_RESULT:
        name = str(p.get("name", ""))
        tid = str(p.get("tool_call_id", ""))
        body = _preview_text(str(p.get("content", "")))
        return f"[{index}] {kind.value}: name={name!r}, id={tid!r}, body={body!r}"
    return f"[{index}] {kind.value}: {p!r}"


def _format_chunks_block(rows: tuple[ChunkRow, ...], *, edge: int) -> str:
    n = len(rows)
    if n == 0:
        return "[]"
    if n <= 2 * edge + 1:
        lines = [_format_chunk_row(i, rows[i]) for i in range(n)]
    else:
        head = [_format_chunk_row(i, rows[i]) for i in range(edge)]
        tail = [_format_chunk_row(i, rows[i]) for i in range(n - edge, n)]
        omitted = n - 2 * edge
        lines = head + [f"... ({omitted} chunks omitted) ..."] + tail
    inner = ",\n    ".join(lines)
    return "[\n    " + inner + "\n  ]"


@dataclass(slots=True)
class Session:
    """Chunk transcript (:attr:`chunk_table`), optional sandbox, and lineage metadata.

    Sandbox placement is **torch-like**: :attr:`sandbox_backend` is ``None`` until
    you call :meth:`to` (or :meth:`bind_sandbox`). The handle in :attr:`sandbox` is
    opened **lazily** on first use (:meth:`require_sandbox` or entering
    ``with session:``). Every ``self.sandbox`` slot counts as one reference on the
    :class:`~rath.backend.BackendSandbox` instance; :meth:`close_sandbox` drops it,
    and the backend ``close`` is called only when the reference count reaches zero.
    ``with session:`` is optional; when used, the outermost exit calls
    :meth:`close_sandbox`.

    Sharing semantics: :func:`~rath.session.loop.run_session_loop`,
    :func:`~rath.session.compress.run_session_compress`, :meth:`fork`,
    :meth:`detach`, and :meth:`merge` all bind the new session to the **same**
    sandbox object as the source (refcount + 1). The source session keeps its
    reference. :meth:`detach` differs from :meth:`fork` only in lineage:
    :meth:`fork` records ``parent_session_ids=(self.id,)``; :meth:`detach`
    records an empty parent tuple. :meth:`merge` always keeps ``self.sandbox``
    (the first session's); ``other.sandbox`` is ignored, and ``other`` keeps
    its own reference.

    Flat lineage (preferred graph substrate): :attr:`parent_session_ids` (ordered
    parents), :attr:`lineage_operator`, :attr:`lineage_kind`, :attr:`lineage_extras`.
    :attr:`lineage` is an optional legacy DTO tying loop outputs to producer sessions.
    """

    chunk_table: ChunkTable
    id: UUID = field(default_factory=uuid4)
    sandbox: BackendSandbox | None = None
    sandbox_backend: str | None = None
    _sandbox_open_spec: BackendSandboxSpec | None = field(default=None, repr=False)
    _cm_depth: int = field(default=0, repr=False)
    lineage: SessionLineage | None = None
    parent_session_ids: tuple[UUID, ...] = ()
    lineage_operator: str = "implicit"
    lineage_kind: LineageKind = LineageKind.UNKNOWN
    lineage_extras: tuple[tuple[str, Any], ...] = ()
    # Running total of LLM token usage attributed to this session. Set by
    # run_session_loop / run_session_compress after each completion. ``None``
    # before any completion has been folded in. Not propagated by fork() /
    # detach() - derived sessions start at zero.
    cumulative_usage: RathLLMTokenUsage | None = None

    @classmethod
    def from_agent_prompt(cls, prompt: str) -> Session:
        from rath.session.chunk import system_text_chunk

        return cls(
            chunk_table=ChunkTable(rows=(system_text_chunk(prompt),)),
        )

    @classmethod
    def from_user_message(cls, text: str) -> Session:
        from rath.session.chunk import user_text_chunk

        return cls(
            chunk_table=ChunkTable(rows=(user_text_chunk(text),)),
        )

    @classmethod
    def create(cls, kind: str = "user", text: str = "") -> Session:
        """Friendly single-entry constructor with lineage stamping.

        ``kind`` is one of:

        - ``"user"`` — single USER chunk holding ``text``; stamps ``LEAF_USER``.
        - ``"system"`` — single SYSTEM chunk holding ``text``; stamps ``LEAF_SYSTEM``.
        - ``"empty"`` — zero-row transcript; ``text`` is ignored; no lineage stamp.

        The returned session is **unbound** (no sandbox). Chain ``.to(backend)``
        to pick a backend; the handle opens lazily on first use or
        ``with session:``.
        """
        from rath.session.chunk import system_text_chunk, user_text_chunk

        if kind == "user":
            s = cls(chunk_table=ChunkTable(rows=(user_text_chunk(text),)))
            LineageRecorder.stamp_new_session(
                s,
                parent_session_ids=(),
                lineage_operator="Session.create",
                lineage_kind=LineageKind.LEAF_USER,
                lineage_extras=(("source", "Session.create"),),
            )
            return s
        if kind == "system":
            s = cls(chunk_table=ChunkTable(rows=(system_text_chunk(text),)))
            LineageRecorder.stamp_new_session(
                s,
                parent_session_ids=(),
                lineage_operator="Session.create",
                lineage_kind=LineageKind.LEAF_SYSTEM,
                lineage_extras=(("source", "Session.create"),),
            )
            return s
        if kind == "empty":
            return cls(chunk_table=ChunkTable(rows=()))
        raise ValueError(
            f"Session.create: unknown kind {kind!r}; "
            "expected one of 'user', 'system', 'empty'"
        )

    def to(
        self,
        backend: str = "local",
        *,
        spec: BackendSandboxSpec | str | None = None,
    ) -> Session:
        """Close any current handle, set target backend, and return ``self`` (chainable).

        ``spec`` may be a :class:`~rath.backend.abc.BackendSandboxSpec` or a string
        path interpreted as ``BackendSandboxSpec(working_dir=...)`` (e.g. ``"."``).
        """

        self.close_sandbox()
        self.sandbox_backend = backend
        self._sandbox_open_spec = _coerce_sandbox_open_spec(spec)
        return self

    def close_sandbox(self) -> Session:
        """Drop this session's sandbox reference; close when refcount hits zero."""

        if self.sandbox is not None and not self.sandbox.closed:
            self.sandbox.release()
        self.sandbox = None
        return self

    def _ensure_sandbox(self) -> None:
        if self.sandbox is not None and not self.sandbox.closed:
            return
        if self.sandbox is not None and self.sandbox.closed:
            self.sandbox = None
        if self.sandbox_backend is None:
            raise RuntimeError(
                'session has no sandbox backend; call session.to("local") '
                "or session.bind_sandbox(...)"
            )
        open_spec = _coerce_sandbox_open_spec(self._sandbox_open_spec)
        sb = get(self.sandbox_backend).open(open_spec)
        sb.acquire()
        self.sandbox = sb

    def __enter__(self) -> Session:
        if self._cm_depth == 0:
            self._ensure_sandbox()
        self._cm_depth += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._cm_depth -= 1
        if self._cm_depth == 0:
            self.close_sandbox()

    def require_sandbox(self) -> BackendSandbox:
        if self.sandbox is not None:
            if self.sandbox.closed:
                raise RuntimeError("session sandbox is closed")
            return self.sandbox
        if self.sandbox_backend is None:
            raise RuntimeError(
                'session has no sandbox backend; call session.to("local") '
                "or session.bind_sandbox(...)"
            )
        self._ensure_sandbox()
        assert self.sandbox is not None
        return self.sandbox

    def bind_sandbox(self, sandbox: BackendSandbox) -> Session:
        """Take a reference to ``sandbox`` (refcount + 1); release the previous one."""
        if self.sandbox is sandbox:
            return self
        if self.sandbox is not None and not self.sandbox.closed:
            self.sandbox.release()
        sandbox.acquire()
        self.sandbox = sandbox
        self.sandbox_backend = sandbox.backend.name
        self._sandbox_open_spec = sandbox.spec
        return self

    def fork(self) -> "Session":
        """Duplicate transcript; share the same sandbox reference (refcount + 1)."""

        rows = tuple(self.chunk_table.rows)
        forked = Session(
            chunk_table=ChunkTable(rows=rows),
            sandbox_backend=self.sandbox_backend,
            _sandbox_open_spec=self._sandbox_open_spec,
        )
        if self.sandbox is not None and not self.sandbox.closed:
            forked.bind_sandbox(self.sandbox)
        LineageRecorder.stamp_new_session(
            forked,
            parent_session_ids=(self.id,),
            lineage_operator="Session.fork",
            lineage_kind=LineageKind.OP_FORK,
        )
        return forked

    def detach(self) -> "Session":
        """Duplicate transcript with a fresh lineage root; share the sandbox reference."""

        rows = tuple(self.chunk_table.rows)
        detached = Session(
            chunk_table=ChunkTable(rows=rows),
            sandbox_backend=self.sandbox_backend,
            _sandbox_open_spec=self._sandbox_open_spec,
        )
        if self.sandbox is not None and not self.sandbox.closed:
            detached.bind_sandbox(self.sandbox)
        LineageRecorder.stamp_new_session(
            detached,
            parent_session_ids=(),
            lineage_operator="Session.detach",
            lineage_kind=LineageKind.OP_DETACH,
            lineage_extras=(),
        )
        return detached

    def merge(self, other: "Session") -> "Session":
        """Concatenate ``self.rows + other.rows`` into a new session.

        The merged session **always keeps** ``self.sandbox`` — the first
        session's. ``other.sandbox`` is ignored regardless of whether it is
        the same instance, a different one, or ``None``; ``other`` keeps its
        own reference. Refcount on ``self.sandbox`` is bumped by 1 when set.
        :attr:`cumulative_usage` is summed across both inputs. Lineage parents
        are ``(self.id, other.id)``, kind is :attr:`LineageKind.OP_MERGE`.

        The only remaining hard constraint: when **both** sessions are unbound
        and they declare different ``sandbox_backend`` targets, merging is
        ambiguous — raises :class:`ValueError`.
        """
        if (
            self.sandbox is None
            and other.sandbox is None
            and self.sandbox_backend != other.sandbox_backend
        ):
            raise ValueError(
                "cannot merge unbound sessions targeting different backends: "
                f"{self.sandbox_backend!r} vs {other.sandbox_backend!r}"
            )
        merged_rows = self.chunk_table.rows + other.chunk_table.rows
        merged_usage = add_usage(self.cumulative_usage, other.cumulative_usage)
        merged = Session(
            chunk_table=ChunkTable(rows=merged_rows),
            sandbox_backend=self.sandbox_backend,
            _sandbox_open_spec=self._sandbox_open_spec,
            cumulative_usage=merged_usage,
        )
        if self.sandbox is not None and not self.sandbox.closed:
            merged.bind_sandbox(self.sandbox)
        LineageRecorder.stamp_new_session(
            merged,
            parent_session_ids=(self.id, other.id),
            lineage_operator="Session.merge",
            lineage_kind=LineageKind.OP_MERGE,
        )
        return merged

    def __str__(self) -> str:
        cls_name = type(self).__name__
        block = _format_chunks_block(
            self.chunk_table.rows, edge=_SESSION_REPR_CHUNK_EDGE
        )
        return (
            f"{cls_name}(\n  chunks={block},\n  operator={self.lineage_operator!r},\n)"
        )

    def __repr__(self) -> str:
        return self.__str__()
