"""OpenViking I/O and lifecycle dispatch against a real OpenViking server.

Consolidated from (every test function name preserved verbatim):
- test_openviking_lifecycle.py   (open/close/store_count)
- test_openviking_fs_ops.py      (Read / List / Tree against seeded resources)
- test_openviking_mutations.py   (Write / Resource / Commit)
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import Iterator

import pytest

from rath.memory import (
    MemoryCommitResult,
    MemoryEntry,
    MemoryExecutionFailure,
    MemoryListResult,
    MemoryOpCommit,
    MemoryOpList,
    MemoryOpRead,
    MemoryOpResource,
    MemoryOpTree,
    MemoryOpWrite,
    MemoryReadResult,
    MemoryStore,
    MemoryStoreSpec,
    MemoryWriteResult,
)
from rath.memory.adapters.openviking import OpenVikingBackend
from tests.memory.backends.conftest import add_resource_with_retry

pytestmark = pytest.mark.openviking


# ---------------------------------------------------------------------------
# fixtures shared across this module
# ---------------------------------------------------------------------------


@pytest.fixture
def http_spec(openviking_url: str, openviking_root_api_key: str) -> MemoryStoreSpec:
    return MemoryStoreSpec(
        namespace="user",
        account_id="default",
        user_id="default",
        agent_id="default",
        options={"url": openviking_url, "api_key": openviking_root_api_key},
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
def seeded_resource_namespace(
    openviking_url: str, openviking_root_api_key: str
) -> dict[str, str]:
    """Drop a fixture file into a fresh ``viking://resources/<ns>/`` directory."""
    import openviking as _ov

    ns = "ofs_" + uuid.uuid4().hex[:8]
    content = "OpenRath FS ops test fixture content."
    client = _ov.SyncHTTPClient(
        url=openviking_url,
        api_key=openviking_root_api_key,
        account="default",
        user_id="default",
        agent_id="default",
    )
    client.initialize()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(content)
            local_path = fh.name
        try:
            result = add_resource_with_retry(
                client,
                local_path,
                to=f"viking://resources/{ns}/",
            )
        finally:
            os.unlink(local_path)
        listing = client.ls(f"viking://resources/{ns}")
        files = [e for e in listing if not e.get("isDir")]
        assert files, f"seed failed: no file produced under {ns}; {result!r}"
        file_uri = files[0]["uri"]
    finally:
        client.close()
    return {
        "namespace_uri": f"viking://resources/{ns}",
        "file_uri": file_uri,
        "content": content,
    }


def _seed_writable_memory(openviking_url: str, openviking_root_api_key: str) -> str:
    """Seed a writable memory file via add_resource. Returns the file URI."""
    import openviking as _ov

    ns = "omut_" + uuid.uuid4().hex[:8]
    client = _ov.SyncHTTPClient(
        url=openviking_url,
        api_key=openviking_root_api_key,
        account="default",
        user_id="default",
        agent_id="default",
    )
    client.initialize()
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as fh:
            fh.write("# seed\nOriginal content.")
            local = fh.name
        try:
            add_resource_with_retry(
                client,
                local,
                to=f"viking://resources/{ns}/",
            )
        finally:
            os.unlink(local)
        listing = client.ls(f"viking://resources/{ns}")
        files = [e for e in listing if not e.get("isDir")]
        assert files, "seed failed"
        return files[0]["uri"]
    finally:
        client.close()


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


def test_open_returns_memory_store_handle(http_spec: MemoryStoreSpec) -> None:
    backend = OpenVikingBackend()
    try:
        store = backend.open(http_spec)
        assert isinstance(store, MemoryStore)
        assert store.handle  # non-empty
        assert store.spec is http_spec
        assert store.closed is False
        assert backend.store_count() == 1
    finally:
        backend.close(store)


def test_store_count_tracks_multiple_opens(http_spec: MemoryStoreSpec) -> None:
    backend = OpenVikingBackend()
    s1 = backend.open(http_spec)
    s2 = backend.open(http_spec)
    try:
        assert s1.handle != s2.handle
        assert backend.store_count() == 2
    finally:
        backend.close(s1)
        backend.close(s2)
    assert backend.store_count() == 0


def test_close_marks_store_closed_and_decrements_count(
    http_spec: MemoryStoreSpec,
) -> None:
    backend = OpenVikingBackend()
    store = backend.open(http_spec)
    assert backend.store_count() == 1
    backend.close(store)
    assert store.closed is True
    assert backend.store_count() == 0


def test_close_is_idempotent(http_spec: MemoryStoreSpec) -> None:
    backend = OpenVikingBackend()
    store = backend.open(http_spec)
    backend.close(store)
    backend.close(store)  # second call must not raise
    assert store.closed is True
    assert backend.store_count() == 0


def test_open_embedded_mode_or_skip(tmp_path) -> None:
    """Exercise embedded mode if the ``pyagfs`` binding-client is available.

    The embedded backend (`openviking.OpenViking(path=...)`) needs a
    platform-specific Go binding wheel. When that wheel is absent the
    constructor raises ImportError -- the adapter is required to surface
    that as ``MemoryBackendError`` ("openviking embedded mode requires
    pyagfs binding-client"), which this test catches and converts to a
    SKIP. We do **not** mock around the missing wheel: if the platform
    can't run embedded, that's the user's environment, not our problem.
    """
    from rath.memory.errors import MemoryBackendError

    spec = MemoryStoreSpec(options={"path": str(tmp_path / "ov_embedded")})
    backend = OpenVikingBackend()
    try:
        store = backend.open(spec)
    except MemoryBackendError as exc:
        pytest.skip(f"embedded mode unavailable: {exc}")
    try:
        assert isinstance(store, MemoryStore)
        assert backend.store_count() == 1
    finally:
        backend.close(store)


# ---------------------------------------------------------------------------
# read / list / tree (against seeded resource)
# ---------------------------------------------------------------------------


def test_read_detail_returns_full_content(
    store: MemoryStore, seeded_resource_namespace: dict[str, str]
) -> None:
    op = MemoryOpRead(uri=seeded_resource_namespace["file_uri"], level="detail")
    result = store.dispatch(op)
    assert isinstance(result, MemoryReadResult)
    assert result.level == "detail"
    assert result.uri == op.uri
    text = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
    assert seeded_resource_namespace["content"] in text


def test_read_abstract_on_directory_returns_summary(
    store: MemoryStore, seeded_resource_namespace: dict[str, str]
) -> None:
    """The OpenViking server only exposes abstract/overview on directories
    (files raise FailedPreconditionError). The adapter passes the level
    straight through; this test pins that behaviour for L0 against a dir."""
    op = MemoryOpRead(uri=seeded_resource_namespace["namespace_uri"], level="abstract")
    result = store.dispatch(op)
    assert isinstance(result, MemoryReadResult)
    assert result.level == "abstract"
    text = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
    assert isinstance(text, str)


def test_read_overview_on_directory_returns_navigable_summary(
    store: MemoryStore, seeded_resource_namespace: dict[str, str]
) -> None:
    op = MemoryOpRead(uri=seeded_resource_namespace["namespace_uri"], level="overview")
    result = store.dispatch(op)
    assert isinstance(result, MemoryReadResult)
    assert result.level == "overview"
    text = result.data if isinstance(result.data, str) else result.data.decode("utf-8")
    assert isinstance(text, str)


def test_list_returns_entries_for_namespace(
    store: MemoryStore, seeded_resource_namespace: dict[str, str]
) -> None:
    op = MemoryOpList(uri=seeded_resource_namespace["namespace_uri"])
    result = store.dispatch(op)
    assert isinstance(result, MemoryListResult)
    assert result.entries, "expected at least one entry"
    file_entry = next(
        (e for e in result.entries if e.uri == seeded_resource_namespace["file_uri"]),
        None,
    )
    assert file_entry is not None
    assert isinstance(file_entry, MemoryEntry)
    assert file_entry.is_dir is False
    assert file_entry.size is not None and file_entry.size > 0


def test_tree_returns_flattened_entries(
    store: MemoryStore, seeded_resource_namespace: dict[str, str]
) -> None:
    op = MemoryOpTree(uri=seeded_resource_namespace["namespace_uri"], depth=3)
    result = store.dispatch(op)
    assert isinstance(result, MemoryListResult)
    uris = {e.uri for e in result.entries}
    assert seeded_resource_namespace["file_uri"] in uris


def test_read_missing_uri_returns_not_found_failure(store: MemoryStore) -> None:
    op = MemoryOpRead(
        uri="viking://user/default/__definitely_does_not_exist_" + uuid.uuid4().hex,
        level="detail",
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind == "not_found"


# ---------------------------------------------------------------------------
# write / resource / commit
# ---------------------------------------------------------------------------


def test_write_updates_existing_memory_file(
    store: MemoryStore,
    openviking_url: str,
    openviking_root_api_key: str,
) -> None:
    seed_uri = _seed_writable_memory(openviking_url, openviking_root_api_key)
    new_content = "Replaced content: dark mode confirmed."
    op = MemoryOpWrite(uri=seed_uri, content=new_content, wait=False)
    result = store.dispatch(op)
    assert isinstance(result, MemoryWriteResult)
    assert result.uri == seed_uri
    assert result.bytes_written == len(new_content.encode("utf-8"))
    # Round-trip
    read = store.dispatch(MemoryOpRead(uri=seed_uri, level="detail"))
    text = read.data if isinstance(read.data, str) else read.data.decode("utf-8")
    assert text == new_content


def test_write_to_invalid_scope_returns_failure(store: MemoryStore) -> None:
    op = MemoryOpWrite(
        uri="viking://bogus_scope_xyz/x.txt",
        content="x",
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryExecutionFailure)
    assert result.kind == "invalid_uri"


def test_resource_ingest_creates_file(store: MemoryStore) -> None:
    ns = "ores_" + uuid.uuid4().hex[:8]
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as fh:
        fh.write("Resource ingest test content for OpenRath.")
        local = fh.name
    try:
        op = MemoryOpResource(
            source=local,
            target_uri=f"viking://resources/{ns}/",
            wait=True,
            timeout_seconds=180.0,
        )
        result = store.dispatch(op)
    finally:
        os.unlink(local)
    assert isinstance(result, MemoryWriteResult)
    assert result.uri  # non-empty


def test_commit_archives_session_and_returns_task_id(
    store: MemoryStore,
) -> None:
    sid = "ocommit_" + uuid.uuid4().hex[:8]
    op = MemoryOpCommit(
        session_id=sid,
        messages=(
            {
                "role": "user",
                "content": "Please remember: my favorite test fixture phrase is 'rainbow-platypus-9'.",
            },
            {
                "role": "assistant",
                "content": "Noted: 'rainbow-platypus-9' as your favorite test fixture phrase.",
            },
        ),
        wait=False,  # extraction takes ~15s, just check commit accepted
    )
    result = store.dispatch(op)
    assert isinstance(result, MemoryCommitResult)
    assert result.task_id and isinstance(result.task_id, str)
    assert result.archived_uri and result.archived_uri.startswith(
        f"viking://session/{sid}/"
    )
