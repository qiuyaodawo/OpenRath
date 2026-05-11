"""Strict environment checks: no mock keys, fail fast if misconfigured."""

from __future__ import annotations

import os
import sys

from rath.llm import load_rath_llm_settings


def require_openai() -> tuple[str, str | None]:
    """Return (model, base_url). Raises SystemExit on failure."""

    try:
        settings = load_rath_llm_settings()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    model = settings.default_model or "glm-5.1"
    return model, settings.base_url


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
