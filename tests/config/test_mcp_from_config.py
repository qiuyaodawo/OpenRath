"""Resolution / error-path tests for :func:`mcp_tools_from_config`.

No mocks. The success path that launches a real subprocess belongs in
:mod:`tests.integration` — here we only assert that the config-driven
dispatch decisions raise the documented :class:`KeyError` variants.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rath.config.schema import MCPServerConfig
from rath.config.store import ConfigStore
from rath.flow.tool.mcp_adapter import mcp_tools_from_config


def _store_with_servers(tmp_path: Path, **servers: MCPServerConfig) -> ConfigStore:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    for name, entry in servers.items():
        store.config.mcp.servers[name] = entry
    store.save()
    return ConfigStore(path=cfg_path)


def test_unknown_server_name_raises_keyerror(tmp_path: Path) -> None:
    store = _store_with_servers(
        tmp_path,
        fs=MCPServerConfig(command=["python", "-m", "mcp_server_filesystem"]),
    )
    with pytest.raises(KeyError) as exc_info:
        mcp_tools_from_config("not-in-config", store=store)
    message = str(exc_info.value)
    assert "not-in-config" in message
    assert "fs" in message


def test_no_name_with_empty_default_enabled_raises(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.json"
    store = ConfigStore(path=cfg_path)
    store.save()
    reloaded = ConfigStore(path=cfg_path)
    with pytest.raises(KeyError, match="mcp.default_enabled is empty"):
        mcp_tools_from_config(store=reloaded)


def test_no_name_with_multiple_default_enabled_raises(tmp_path: Path) -> None:
    store = _store_with_servers(
        tmp_path,
        a=MCPServerConfig(command=["a"]),
        b=MCPServerConfig(command=["b"]),
    )
    store.config.mcp.default_enabled = ["a", "b"]
    store.save()
    reloaded = ConfigStore(path=store.path)
    with pytest.raises(KeyError, match="ambiguous"):
        mcp_tools_from_config(store=reloaded)
