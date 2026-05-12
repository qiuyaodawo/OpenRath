"""Shared helper for examples: build :class:`~rath.llm.provider.Provider` from env."""

from __future__ import annotations

import os

from rath.llm import Provider


def provider_from_env() -> Provider:
    """``OPENAI_API_KEY`` required; ``OPENAI_BASE_URL`` and ``OPENAI_DEFAULT_MODEL`` optional."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the process environment")
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None
    return Provider(api_key=api_key, base_url=base_url, model=model)
