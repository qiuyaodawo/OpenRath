"""Load / mutate / save the on-disk OpenRath config.

Single-process, infrequent-write semantics. No locking, no caching across
processes. Atomic on save (tmp file + ``os.replace``) so a crashed write
never leaves a half-written file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from rath.config.paths import (
    is_project_local,
    resolve_config_dir,
    resolve_config_path,
)
from rath.config.schema import (
    SCHEMA_VERSION,
    LLMProviderConfig,
    MCPServerConfig,
    RathConfig,
)
from rath.config.secrets import (
    chmod_user_only,
    ensure_config_dir_gitignore,
    ensure_project_gitignore_entry,
    warn_if_world_readable,
)

__all__ = ["ConfigStore", "ConfigError"]


class ConfigError(RuntimeError):
    """Raised on schema-validation failure or corrupt JSON.

    The string carries a human-readable summary; the original
    :class:`json.JSONDecodeError` or :class:`pydantic.ValidationError` is
    available via :attr:`__cause__`.
    """


class ConfigStore:
    """Round-trip the config file at :attr:`path`.

    The constructor immediately reads the file (or seeds defaults when it
    does not exist), so callers do not need to guard against
    ``FileNotFoundError`` separately. Subsequent reads should mutate
    :attr:`config` directly; call :meth:`save` to persist.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or resolve_config_path()).resolve()
        self._raw_unknown: dict[str, Any] = {}
        self._data: RathConfig = self._load_or_default()

    @classmethod
    def load(cls) -> "ConfigStore":
        """Build a store from the resolved default path."""
        return cls()

    @property
    def config(self) -> RathConfig:
        """The parsed config. Mutate fields in place, then call :meth:`save`."""
        return self._data

    def save(self) -> None:
        """Atomically persist ``self.config`` to :attr:`path`.

        Side-effects:
        - Creates parent directory if missing.
        - Writes ``<path>.tmp`` then ``os.replace`` — durable on POSIX and
          Windows.
        - ``chmod 600`` on POSIX so secrets are not world-readable.
        - Writes a deny-all ``.gitignore`` next to the config (idempotent).
        - When the config dir is the project-local ``./.openrath/``, also
          appends ``.openrath/`` to the surrounding project ``.gitignore``
          (idempotent; skipped when no project gitignore exists).
        """
        config_dir = self.path.parent
        ensure_config_dir_gitignore(config_dir)
        if is_project_local(config_dir):
            ensure_project_gitignore_entry(Path.cwd())

        payload = self._merged_payload()
        text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(text + "\n", encoding="utf-8")
        tmp.replace(self.path)
        chmod_user_only(self.path)

    # --- LLM helpers ------------------------------------------------------

    def get_llm_provider(self, name: str | None) -> LLMProviderConfig:
        """Return the named LLM provider entry.

        ``name=None`` falls back to :attr:`LLMConfig.default_provider`.
        Raises :class:`KeyError` with the available names when the lookup
        fails — callers display this directly to the user.
        """
        target = name or self._data.llm.default_provider
        if target is None:
            raise KeyError(
                "no LLM provider name given and no llm.default_provider set "
                f"in {self.path}",
            )
        try:
            return self._data.llm.providers[target]
        except KeyError as e:
            available = sorted(self._data.llm.providers)
            raise KeyError(
                f"LLM provider {target!r} not found in {self.path}; "
                f"available: {available}",
            ) from e

    def find_provider_by_kind(self, kind: str) -> LLMProviderConfig | None:
        """Return the best config entry for ``provider_kind=kind``, or ``None``.

        Priority:
        1. The ``default_provider`` if it is set and matches ``kind``.
        2. Otherwise the first entry (insertion order) whose
           ``provider_kind`` matches.

        Used by per-provider chat clients as their tier-3 fallback so a
        user with both ``zai`` (openai) and ``claude`` (anthropic) entries
        gets the right key per client, regardless of which is the default.
        """
        default_name = self._data.llm.default_provider
        if default_name is not None:
            default_entry = self._data.llm.providers.get(default_name)
            if default_entry is not None and default_entry.provider_kind == kind:
                return default_entry
        for entry in self._data.llm.providers.values():
            if entry.provider_kind == kind:
                return entry
        return None

    # --- MCP helpers ------------------------------------------------------

    def get_mcp_server(self, name: str) -> MCPServerConfig:
        """Return the named MCP server entry."""
        try:
            return self._data.mcp.servers[name]
        except KeyError as e:
            available = sorted(self._data.mcp.servers)
            raise KeyError(
                f"MCP server {name!r} not found in {self.path}; available: {available}",
            ) from e

    def enabled_mcp_servers(self) -> list[MCPServerConfig]:
        """Return ``MCPServerConfig`` for every name in ``default_enabled``.

        Missing names raise :class:`KeyError` from :meth:`get_mcp_server`.
        """
        return [self.get_mcp_server(n) for n in self._data.mcp.default_enabled]

    # --- Internals --------------------------------------------------------

    def _load_or_default(self) -> RathConfig:
        if not self.path.is_file():
            return RathConfig()
        warn_if_world_readable(self.path)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(
                f"{self.path} is not valid JSON (line {e.lineno}, col {e.colno}): "
                f"{e.msg}",
            ) from e
        if not isinstance(raw, dict):
            raise ConfigError(
                f"{self.path} top-level must be a JSON object, got "
                f"{type(raw).__name__}",
            )
        try:
            return RathConfig.model_validate(raw)
        except ValidationError as e:
            raise ConfigError(f"{self.path} failed schema validation: {e}") from e

    def _merged_payload(self) -> dict[str, Any]:
        """Serialize ``self._data`` ensuring known keys are present.

        Pydantic ``extra="allow"`` already preserves unknown fields, so a
        plain ``model_dump`` round-trips everything we read in. We do force
        ``version`` to the current ``SCHEMA_VERSION`` on every write — older
        files get upgraded transparently when re-saved.
        """
        payload = self._data.model_dump(mode="json")
        payload["version"] = SCHEMA_VERSION
        return payload


def default_store() -> ConfigStore:
    """Convenience: ``ConfigStore.load()`` with the resolved default path."""
    return ConfigStore(resolve_config_path())


# Re-exported here as a convenience so callers can do
# ``from rath.config.store import resolve_config_dir`` without importing both.
__all__ += ["default_store", "resolve_config_dir"]
