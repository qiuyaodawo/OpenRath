"""Persistent local configuration for OpenRath.

Stored as JSON at ``~/.openrath/config.json`` by default, overridable to
``./.openrath/config.json`` (project-local marker) or
``$OPENRATH_HOME/config.json`` (explicit override).

Public surface:

* :func:`resolve_config_dir` / :func:`resolve_config_path` — locate the file.
* :class:`ConfigStore` — read/round-trip/write the JSON document.
* :class:`RathConfig` + section / entry dataclasses — Pydantic v2 schema.
* :exc:`ConfigError` — corrupt JSON or schema-validation failure.

This package is intentionally **lazy**: importing :mod:`rath` does NOT touch
the filesystem here. Reads happen only when the caller constructs a
:class:`ConfigStore` (or calls :meth:`rath.llm.Provider.from_config` /
:func:`rath.flow.tool.mcp_adapter.mcp_tools_from_config`).
"""

from rath.config.paths import (
    CONFIG_FILENAME,
    OPENRATH_HOME_ENV,
    PROJECT_MARKER_DIR,
    USER_DIR_NAME,
    is_project_local,
    resolve_config_dir,
    resolve_config_path,
)
from rath.config.schema import (
    SCHEMA_VERSION,
    LLMConfig,
    LLMProviderConfig,
    MCPConfig,
    MCPServerConfig,
    RathConfig,
)
from rath.config.store import ConfigError, ConfigStore, default_store

__all__ = [
    # Paths
    "resolve_config_dir",
    "resolve_config_path",
    "is_project_local",
    "OPENRATH_HOME_ENV",
    "CONFIG_FILENAME",
    "PROJECT_MARKER_DIR",
    "USER_DIR_NAME",
    # Schema
    "RathConfig",
    "LLMConfig",
    "LLMProviderConfig",
    "MCPConfig",
    "MCPServerConfig",
    "SCHEMA_VERSION",
    # Store
    "ConfigStore",
    "ConfigError",
    "default_store",
]
