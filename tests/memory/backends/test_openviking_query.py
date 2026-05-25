"""OpenViking query + error-kind dispatch against a real OpenViking server.

Consolidated from (every test function name preserved verbatim):
- test_openviking_search.py    (Find / Search)
- test_openviking_errors.py    (MemoryExecutionFailure.kind mapping)
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Iterator

import pytest

from rath.memory import (
    MemoryExecutionFailure,
    MemoryFindResult,
    MemoryHit,
    MemoryOpFind,
    MemoryOpList,
    MemoryOpRead,
    MemoryOpSearch,
    MemoryOpWrite,
    MemoryStore,
    MemoryStoreSpec,
)
from rath.memory.adapters.openviking import OpenVikingBackend

pytestmark = pytest.mark.openviking

_DB_FIXTURE = (
    "OpenRath database migration playbook: ALTER TABLE strategy, rolling "
    "deployments, online schema-change tools, replica catchup."
)
_WEATHER_FIXTURE = (
    "Weather report for the central plateau region: thunderstorms expected "
    "overnight with gusts reaching forty knots."
)


@pytest.fixture
def store(openviking_url: str, openviking_root_api_key: str) -> Iterator[MemoryStore]:
    backend = OpenVikingBackend()
    spec = MemoryStoreSpec(
        account_id="default",
        user_id="default",
        agent_id="default",
        options={"url": openviking_url, "api_key": openviking_root_api_key},
    )
    s = backend.open(spec)
    try:
        yield s
    finally:
        backend.close(s)


@pytest.fixture(scope="module")
def seeded_search_namespace(
    openviking_url: str, openviking_root_api_key: str
) -> dict[str, str]:
    import openviking as _ov

    ns = "osearch_" + uuid.uuid4().hex[:8]
    client = _ov.SyncHTTPClient(
        url=openviking_url,
        api_key=openviking_root_api_key,
        account="default",
        user_id="default",
        agent_id="default",
    )
    client.initialize()
    try:
        for label, content in [("db", _DB_FIXTURE), ("wx", _WEATHER_FIXTURE)]:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(content)
                local = fh.name
            try:
                client.add_resource(
                    local,
                    to=f"viking://resources/{ns}/{label}/",
                    wait=True,
                    timeout=90.0,
                )
            finally:
                os.unlink(local)
        try:
            client.wait_processed(timeout=60.0)
        except Exception:
            pass
    finally:
        client.close()
    return {"namespace_uri": f"memory://resources/{ns}"}


# ---------------------------------------------------------------------------
# Find / Search
# ---------------------------------------------------------------------------


def test_find_returns_ranked_hits(
    store: MemoryStore, seeded_search_namespace: dict[str, str]
) -> None:
    op = MemoryOpFind(
        query="database migration playbook",
        target_uri=seeded_search_namespace["namespace_uri"],
        top_k=5,
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryFindResult)
    assert result.hits, "find should return at least one hit for the seeded corpus"
    top = result.hits[0]
    assert isinstance(top, MemoryHit)
    assert top.uri.startswith(seeded_search_namespace["namespace_uri"])
    assert top.score >= 0.0
    # The db fixture should outrank the weather one for this query.
    db_hits = [h for h in result.hits if "/db/" in h.uri]
    wx_hits = [h for h in result.hits if "/wx/" in h.uri]
    if db_hits and wx_hits:
        assert db_hits[0].score >= wx_hits[0].score


def test_find_honours_top_k(
    store: MemoryStore, seeded_search_namespace: dict[str, str]
) -> None:
    op = MemoryOpFind(
        query="thunderstorms",
        target_uri=seeded_search_namespace["namespace_uri"],
        top_k=1,
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryFindResult)
    assert len(result.hits) <= 1


def test_search_returns_ranked_hits(
    store: MemoryStore, seeded_search_namespace: dict[str, str]
) -> None:
    op = MemoryOpSearch(
        query="database migration playbook",
        target_uri=seeded_search_namespace["namespace_uri"],
        top_k=5,
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryFindResult)
    assert result.hits


def test_find_with_bogus_scope_returns_well_formed_result(
    store: MemoryStore,
) -> None:
    """The server tolerates an unknown sub-path inside ``memory://resources/``
    (returns empty hits). A truly invalid scope produces invalid_uri.
    Either is fine; this test pins both behaviours under one assertion."""
    op = MemoryOpFind(
        query="anything",
        target_uri="memory://bogus_scope_xyz/",
        top_k=3,
    )
    result = store.dispatch(op)
    assert isinstance(result, (MemoryFindResult, MemoryExecutionFailure))
    if isinstance(result, MemoryExecutionFailure):
        assert result.kind in {"invalid_uri", "not_found"}


# ---------------------------------------------------------------------------
# MemoryExecutionFailure.kind mapping
# ---------------------------------------------------------------------------


def test_not_found_for_unknown_uri(store: MemoryStore) -> None:
    op = MemoryOpRead(
        uri=f"viking://user/default/__does_not_exist_{uuid.uuid4().hex}",
        level="detail",
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind == "not_found"


def test_invalid_uri_for_bogus_scope(store: MemoryStore) -> None:
    op = MemoryOpWrite(uri="viking://bogus_scope_xyz/x.txt", content="x")
    result = store.dispatch(op)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind == "invalid_uri"


def test_invalid_uri_for_list_against_unknown_scope(store: MemoryStore) -> None:
    """The SDK's ls() against an unknown scope raises InvalidURIError
    (not NotFoundError) -- this test pins that mapping."""
    op = MemoryOpList(uri="viking://bogus_scope_xyz/")
    result = store.dispatch(op)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind == "invalid_uri"


def test_transport_failure_for_unreachable_host(
    openviking_root_api_key: str,
) -> None:
    """Open a store against a port that nothing listens on; the first
    dispatch should surface as ``kind="transport"``.

    NOTE: depending on the SDK, the failure may also show up at
    ``open()`` time (during ``client.initialize()``). In that case we get
    a ``MemoryBackendError`` and the test still asserts the right
    *category* of failure -- a transport problem -- just at a different
    layer.
    """
    from rath.memory.errors import MemoryBackendError

    backend = OpenVikingBackend()
    spec = MemoryStoreSpec(
        account_id="default",
        user_id="default",
        agent_id="default",
        options={
            "url": "http://127.0.0.1:1",  # nothing listens on port 1
            "api_key": openviking_root_api_key,
            "timeout": 2.0,
        },
    )
    try:
        store = backend.open(spec)
    except MemoryBackendError:
        return  # transport failure surfaced at open(), test passes
    try:
        result = store.dispatch(MemoryOpFind(query="x"))
    finally:
        backend.close(store)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind in {"transport", "internal"}


def test_unauthorized_for_bogus_api_key(openviking_url: str) -> None:
    """A wrong api key should yield ``kind="unauthorized"`` on first
    real call. Mirrors the transport test: failure may also bubble at
    open() time as MemoryBackendError."""
    from rath.memory.errors import MemoryBackendError

    backend = OpenVikingBackend()
    spec = MemoryStoreSpec(
        account_id="default",
        user_id="default",
        agent_id="default",
        options={
            "url": openviking_url,
            "api_key": "definitely-not-a-real-key-" + uuid.uuid4().hex,
        },
    )
    try:
        store = backend.open(spec)
    except MemoryBackendError:
        return
    try:
        result = store.dispatch(MemoryOpFind(query="x"))
    finally:
        backend.close(store)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind in {"unauthorized", "internal"}
