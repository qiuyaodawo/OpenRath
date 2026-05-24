"""OpenViking liveness + metadata canary.

Consolidated from (every test function name preserved verbatim):
- test_openviking_skipgate.py    (health / SDK / api-key probes)
- test_openviking_metadata.py    (backend class metadata; no live server)

If any test here fails or skips, the rest of this directory is dark — the
``_openviking_canary`` autouse fixture under ``conftest.py`` would have
already short-circuited it.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

import rath.memory as memory
from rath.memory import ScopeModel
from rath.memory.adapters import openviking as ov_mod

pytestmark = pytest.mark.openviking


# ---------------------------------------------------------------------------
# liveness canary
# ---------------------------------------------------------------------------


def test_openviking_health(openviking_url: str) -> None:
    with urllib.request.urlopen(f"{openviking_url}/health", timeout=2.0) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    assert payload.get("healthy") is True, payload


def test_openviking_sdk_imports() -> None:
    import openviking as ov

    assert hasattr(ov, "SyncHTTPClient")
    assert hasattr(ov, "OpenViking")


def test_openviking_root_api_key_present(openviking_root_api_key: str) -> None:
    assert openviking_root_api_key  # non-empty


# ---------------------------------------------------------------------------
# class metadata (no live server required beyond SDK import)
# ---------------------------------------------------------------------------


def test_backend_name():
    assert ov_mod.OpenVikingBackend.name == "openviking"


def test_is_available_true_when_sdk_importable():
    assert ov_mod.OpenVikingBackend.is_available() is True


def test_capabilities_describe_hybrid_full_surface():
    caps = ov_mod.OpenVikingBackend.capabilities()
    assert caps.scope_model is ScopeModel.HYBRID
    assert caps.supports_write
    assert caps.supports_read
    assert caps.supports_list
    assert caps.supports_tree
    assert caps.supports_vector_search
    assert caps.supports_intent_search
    assert caps.supports_resource_ingest
    assert caps.supports_session_commit
    assert caps.supports_l0_l1_l2


def test_supported_ops_covers_all_eight():
    ops = ov_mod.OpenVikingBackend.supported_ops()
    assert ops == frozenset(
        {
            memory.MemoryOpWrite,
            memory.MemoryOpRead,
            memory.MemoryOpList,
            memory.MemoryOpTree,
            memory.MemoryOpFind,
            memory.MemoryOpSearch,
            memory.MemoryOpResource,
            memory.MemoryOpCommit,
        }
    )


def test_registers_with_registry_on_import():
    assert "openviking" in memory.list_names()
    assert memory.get_class("openviking") is ov_mod.OpenVikingBackend
