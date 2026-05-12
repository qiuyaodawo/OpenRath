"""Strict environment checks: no mock keys, fail fast if misconfigured."""

from __future__ import annotations

import os
import sys

from rath.llm import Provider


def require_openai_provider() -> Provider:
    """Return a Provider with credentials from the process environment."""

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: OPENAI_API_KEY is not set in the process environment.",
            file=sys.stderr,
        )
        sys.exit(2)
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None
    model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip() or None
    return Provider(api_key=api_key, base_url=base_url, model=model)


def require_alpha_vantage_key() -> str:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "PW2FBNP02JA924O9").strip()
    if not key:
        print(
            "ERROR: ALPHA_VANTAGE_API_KEY is empty. "
            "Get a key at https://www.alphavantage.co/support/#api-key "
            "and export it (TradingAgents documents the same variable).",
            file=sys.stderr,
        )
        sys.exit(3)
    return key
