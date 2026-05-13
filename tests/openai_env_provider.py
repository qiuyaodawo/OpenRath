"""Build :class:`~rath.llm.provider.Provider` from ``OPENAI_*`` for live tests only."""

from __future__ import annotations

import os

from rath.llm.provider import Provider


def live_openai_provider() -> Provider:
    """Read ``OPENAI_API_KEY`` (required), ``OPENAI_BASE_URL``, ``OPENAI_DEFAULT_MODEL``."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the process environment")
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None
    return Provider(api_key=api_key, base_url=base_url, model=model)
