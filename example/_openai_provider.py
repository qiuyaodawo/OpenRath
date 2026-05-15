"""Shared helper for examples: build :class:`Provider` from env or ``~/.openrath/``."""

from __future__ import annotations

import os

from rath.config.store import ConfigStore
from rath.llm import Provider


def provider_from_env() -> Provider:
    """Build a Provider from process env vars, falling back to ``~/.openrath/config.json``.

    Precedence per field: env var → ``llm.default_provider`` entry in config.
    Raises ``ValueError`` only when no source supplies an ``api_key``.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip() or None
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None

    if api_key is None or base_url is None or model is None:
        try:
            store = ConfigStore.load()
            default = store.config.llm.default_provider
            if default is not None:
                entry = store.config.llm.providers.get(default)
                if entry is not None:
                    api_key = api_key or entry.api_key
                    base_url = base_url or entry.base_url
                    model = model or entry.model
        except (FileNotFoundError, RuntimeError):
            pass

    if not api_key:
        raise ValueError(
            "No OpenAI api_key found: export OPENAI_API_KEY or configure "
            "llm.default_provider in ~/.openrath/config.json.",
        )
    return Provider(api_key=api_key, base_url=base_url, model=model)
