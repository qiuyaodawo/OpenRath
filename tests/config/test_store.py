"""Real-filesystem tests for ConfigStore load/save round-trip.

No mocks: every test writes real JSON to ``tmp_path``, reads it back through
the actual :class:`ConfigStore`, and asserts on observed disk state.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from rath.config.paths import PROJECT_MARKER_DIR
from rath.config.schema import (
    LLMProviderConfig,
    MCPServerConfig,
    RathConfig,
)
from rath.config.store import ConfigError, ConfigStore


def test_load_when_file_missing_returns_defaults(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    assert isinstance(store.config, RathConfig)
    assert store.config.llm.providers == {}
    assert store.config.mcp.servers == {}


def test_save_creates_parent_dir(tmp_path: Path) -> None:
    cfg_path = tmp_path / "nested" / "deeper" / "config.json"
    store = ConfigStore(path=cfg_path)
    store.config.llm.providers["x"] = LLMProviderConfig(
        provider_kind="openai", model="gpt-5", api_key="sk-x"
    )
    store.save()
    assert cfg_path.is_file()
    assert (cfg_path.parent / ".gitignore").is_file()


def test_save_load_round_trip_preserves_values(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    s1 = ConfigStore(path=cfg_path)
    s1.config.llm.default_provider = "main"
    s1.config.llm.providers["main"] = LLMProviderConfig(
        provider_kind="anthropic", model="claude-opus-4-7", api_key="sk-ant-rt"
    )
    s1.config.mcp.default_enabled = ["fs"]
    s1.config.mcp.servers["fs"] = MCPServerConfig(
        command=["python", "-m", "mcp_server_filesystem", "/workspace"],
        env={"LOG": "info"},
    )
    s1.save()

    s2 = ConfigStore(path=cfg_path)
    assert s2.config.llm.default_provider == "main"
    main = s2.config.llm.providers["main"]
    assert main.provider_kind == "anthropic"
    assert main.api_key == "sk-ant-rt"
    fs = s2.config.mcp.servers["fs"]
    assert fs.command == ["python", "-m", "mcp_server_filesystem", "/workspace"]
    assert fs.env == {"LOG": "info"}
    assert s2.config.mcp.default_enabled == ["fs"]


def test_round_trip_preserves_unknown_top_level_section(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "version": 1,
                "llm": {"default_provider": None, "providers": {}},
                "mcp": {"default_enabled": [], "servers": {}},
                "future_section": {"x": 1, "nested": {"y": [1, 2, 3]}},
            }
        ),
        encoding="utf-8",
    )
    store = ConfigStore(path=cfg_path)
    store.save()
    on_disk = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert on_disk["future_section"] == {"x": 1, "nested": {"y": [1, 2, 3]}}


def test_corrupt_json_raises_config_error_with_position(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{this is not json", encoding="utf-8")
    with pytest.raises(ConfigError) as exc_info:
        ConfigStore(path=cfg_path)
    assert "line " in str(exc_info.value)
    assert "col " in str(exc_info.value)


def test_non_object_top_level_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a JSON object"):
        ConfigStore(path=cfg_path)


def test_schema_violation_raises_config_error(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps(
            {
                "version": 1,
                "llm": {
                    "providers": {
                        "x": {"provider_kind": "bogus-vendor"},
                    }
                },
                "mcp": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="failed schema validation"):
        ConfigStore(path=cfg_path)


def test_atomic_save_does_not_leave_tmp_behind(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.save()
    assert cfg_path.is_file()
    # The tmp file should have been replaced, not lingering on disk.
    tmp_artifact = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    assert not tmp_artifact.exists()


def test_save_overwrites_existing_file_without_loss(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    s1 = ConfigStore(path=cfg_path)
    s1.config.llm.providers["one"] = LLMProviderConfig(api_key="sk-one")
    s1.save()
    s2 = ConfigStore(path=cfg_path)
    assert s2.config.llm.providers["one"].api_key == "sk-one"
    s2.config.llm.providers["two"] = LLMProviderConfig(api_key="sk-two")
    s2.save()
    s3 = ConfigStore(path=cfg_path)
    assert set(s3.config.llm.providers) == {"one", "two"}


def test_get_llm_provider_named(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.config.llm.providers["x"] = LLMProviderConfig(
        provider_kind="openai", model="gpt-5"
    )
    assert store.get_llm_provider("x").model == "gpt-5"


def test_get_llm_provider_falls_back_to_default(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.config.llm.default_provider = "default-one"
    store.config.llm.providers["default-one"] = LLMProviderConfig(api_key="sk-d")
    assert store.get_llm_provider(None).api_key == "sk-d"


def test_get_llm_provider_no_default_raises(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    with pytest.raises(KeyError, match="no LLM provider name"):
        store.get_llm_provider(None)


def test_find_provider_by_kind_prefers_matching_default(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.llm.providers["claude"] = LLMProviderConfig(
        provider_kind="anthropic", api_key="sk-ant"
    )
    store.config.llm.providers["gpt"] = LLMProviderConfig(
        provider_kind="openai", api_key="sk-oai"
    )
    store.config.llm.default_provider = "gpt"
    # Default kind matches → return default.
    assert store.find_provider_by_kind("openai").api_key == "sk-oai"
    # Default kind doesn't match → first matching entry.
    assert store.find_provider_by_kind("anthropic").api_key == "sk-ant"


def test_find_provider_by_kind_falls_back_to_first_match(tmp_path: Path) -> None:
    """When default_provider is openai but caller wants anthropic, scan."""
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.llm.default_provider = "zai"
    store.config.llm.providers["zai"] = LLMProviderConfig(
        provider_kind="openai", api_key="sk-zai"
    )
    store.config.llm.providers["claude"] = LLMProviderConfig(
        provider_kind="anthropic", api_key="sk-claude"
    )
    out = store.find_provider_by_kind("anthropic")
    assert out is not None
    assert out.api_key == "sk-claude"


def test_find_provider_by_kind_returns_none_when_no_match(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.llm.providers["only-openai"] = LLMProviderConfig(
        provider_kind="openai", api_key="sk-x"
    )
    assert store.find_provider_by_kind("anthropic") is None


def test_find_provider_by_kind_returns_none_on_empty_config(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    assert store.find_provider_by_kind("openai") is None
    assert store.find_provider_by_kind("anthropic") is None


def test_get_llm_provider_unknown_lists_available(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.llm.providers["alpha"] = LLMProviderConfig()
    store.config.llm.providers["beta"] = LLMProviderConfig()
    with pytest.raises(KeyError) as exc_info:
        store.get_llm_provider("gamma")
    message = str(exc_info.value)
    assert "gamma" in message
    assert "alpha" in message
    assert "beta" in message


def test_enabled_mcp_servers_returns_in_order(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.mcp.servers["a"] = MCPServerConfig(command=["a"])
    store.config.mcp.servers["b"] = MCPServerConfig(command=["b"])
    store.config.mcp.default_enabled = ["b", "a"]
    enabled = store.enabled_mcp_servers()
    assert [e.command for e in enabled] == [["b"], ["a"]]


def test_enabled_mcp_servers_unknown_name_raises(tmp_path: Path) -> None:
    store = ConfigStore(path=tmp_path / "config.json")
    store.config.mcp.default_enabled = ["missing"]
    with pytest.raises(KeyError, match="missing"):
        store.enabled_mcp_servers()


def test_save_writes_gitignore_idempotently(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.save()
    gi = cfg_path.parent / ".gitignore"
    first = gi.read_text(encoding="utf-8")
    # Save again; the gitignore should not be re-written or duplicated.
    store.save()
    second = gi.read_text(encoding="utf-8")
    assert first == second
    assert "*" in first
    assert "!.gitignore" in first


def test_project_local_save_amends_project_gitignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When using ./.openrath/, append .openrath/ to the project .gitignore."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENRATH_HOME", raising=False)
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    config_dir = tmp_path / PROJECT_MARKER_DIR
    config_dir.mkdir()
    store = ConfigStore(path=config_dir / "config.json")
    store.save()
    contents = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".openrath/" in contents
    # Idempotent: a second save must not duplicate.
    store.save()
    contents_again = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert contents_again.count(".openrath/") == 1


def test_project_local_save_skips_when_no_project_gitignore(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENRATH_HOME", raising=False)
    config_dir = tmp_path / PROJECT_MARKER_DIR
    config_dir.mkdir()
    store = ConfigStore(path=config_dir / "config.json")
    store.save()
    # No project .gitignore existed; nothing should appear.
    assert not (tmp_path / ".gitignore").exists()


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX permission semantics — Windows uses ACLs",
)
def test_save_restricts_permissions_to_0600(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.config.llm.providers["x"] = LLMProviderConfig(api_key="secret")
    store.save()
    mode = cfg_path.stat().st_mode & 0o777
    assert mode == 0o600
