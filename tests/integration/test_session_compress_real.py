"""Integration tests: live LLM context compression + local sandbox.

Markers: ``integration``, ``live_llm``. Requires ``OPENAI_API_KEY`` and local backend.
"""

from __future__ import annotations

import json
import os

import pytest

from rath.backend import FileContent, get
from rath.flow.tool import flow_tool_files_read, flow_tool_files_write
from rath.llm import RathOpenAIChatClient
from rath.session import (
    ChunkKind,
    ChunkTable,
    DefaultSessionLoopExecutor,
    Session,
    run_session_compress,
    session_registry,
    user_text_chunk,
)
from rath.session.graph import LineageKind
from tests.openai_env_provider import live_openai_provider


def _openai_key_plausible() -> bool:
    return len(os.environ.get("OPENAI_API_KEY", "").strip()) >= 8


_needs_live_llm = pytest.mark.skipif(
    not _openai_key_plausible(),
    reason="OPENAI_API_KEY missing or too short (export in environment)",
)

_needs_local_backend = pytest.mark.skipif(
    not get("local").is_available(),
    reason="local backend not available on this host",
)

pytestmark = [
    _needs_live_llm,
    _needs_local_backend,
    pytest.mark.integration,
    pytest.mark.live_llm,
]


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    yield
    session_registry().set_active(None)


def _concat_user_text(session: Session) -> str:
    parts: list[str] = []
    for row in session.chunk_table.rows:
        if row.kind == ChunkKind.USER:
            parts.append(str(row.payload.get("content", "")))
    return "\n".join(parts)


def _parse_json_object(raw: str) -> dict[str, object]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if ln.strip() not in ("```", "```json")]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise AssertionError("expected JSON object from compress output")
    return data


def test_run_session_compress_structure_and_lineage_real() -> None:
    backend = get("local")
    prov = live_openai_provider()

    filler_rows = tuple(
        user_text_chunk(f"Filler paragraph {i}: discuss widgets, logistics, and noise.")
        for i in range(8)
    )
    markers_row = user_text_chunk(
        "Critical literals that MUST appear in guards array: "
        "RATH_COMPRESS_GUARD_ALPHA and RATH_COMPRESS_GUARD_BETA."
    )
    user = Session(
        chunk_table=ChunkTable(rows=filler_rows + (markers_row,)),
    )
    agent = Session.from_agent_prompt(
        "You are a faithful transcript compressor for downstream LLM context."
    )

    compress_instruction = (
        "Compress the transcript above. Respond with a compact JSON object ONLY "
        '(no markdown fences), keys: "summary" (string) and "guards" (array of '
        "strings). The guards array MUST contain exactly these two strings in order: "
        '"RATH_COMPRESS_GUARD_ALPHA", "RATH_COMPRESS_GUARD_BETA". '
        "The summary must be shorter than the raw transcript."
    )

    with backend.open() as sb:
        user.bind_sandbox(sb)
        executor = DefaultSessionLoopExecutor(RathOpenAIChatClient(prov))
        out = run_session_compress(
            user,
            agent,
            agent_provider=prov,
            executor=executor,
            compress_instruction=compress_instruction,
        )

        assert user.sandbox is sb
        assert out.sandbox is sb and not out.sandbox.closed
        assert sb._refcount == 2
        assert out.parent_session_ids == (user.id, agent.id)
        assert out.lineage_kind == LineageKind.OP_SESSION_COMPRESS
        assert out.lineage_operator == "run_session_compress"
        assert out.lineage is not None
        assert out.lineage.operator == "run_session_compress"

        for row in out.chunk_table.rows:
            assert row.kind == ChunkKind.USER
        assert not any(row.kind == ChunkKind.SYSTEM for row in out.chunk_table.rows)

        before = _concat_user_text(user)
        payload = out.chunk_table.rows[0].payload["content"]
        assert isinstance(payload, str)
        obj = _parse_json_object(payload)
        assert obj["guards"] == [
            "RATH_COMPRESS_GUARD_ALPHA",
            "RATH_COMPRESS_GUARD_BETA",
        ]
        summary = str(obj["summary"])
        assert len(summary) < len(before) * 0.75
        assert len(out.chunk_table.rows) <= len(user.chunk_table.rows)


def test_run_session_compress_sandbox_probe_file_survives_real() -> None:
    backend = get("local")
    prov = live_openai_provider()
    token = "RATH_COMPRESS_PROBE_TOKEN_918273"

    user = Session(
        chunk_table=ChunkTable(
            rows=(
                user_text_chunk("Say hello many times. " * 40),
                user_text_chunk("Remember token for workspace."),
            )
        )
    )
    agent = Session.from_agent_prompt("Compressor.")

    instruction = (
        'Compress to JSON only: {"summary":"one short line"}. '
        "Do not mention filesystem."
    )

    with backend.open() as sb:
        user.bind_sandbox(sb)
        wr = flow_tool_files_write(user, "_rath_compress_probe.txt", token)
        assert wr is not False

        executor = DefaultSessionLoopExecutor(RathOpenAIChatClient(prov))
        out = run_session_compress(
            user,
            agent,
            agent_provider=prov,
            executor=executor,
            compress_instruction=instruction,
        )

        assert user.sandbox is sb
        assert out.sandbox is sb
        raw = flow_tool_files_read(out, "_rath_compress_probe.txt")
        assert isinstance(raw, FileContent)
        body = raw.data
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        assert token in str(body)
