"""Load credentials and defaults from ``.env`` / process environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from rath.utils.env import default_env_file_path, load_dotenv_if_present

__all__ = ["RathLLMSettings", "rath_llm_default_dotenv_path", "load_rath_llm_settings"]


def rath_llm_default_dotenv_path() -> Path:
    """Project ``.env`` path (same as :func:`~rath.utils.env.default_env_file_path`)."""
    return default_env_file_path()


@dataclass(frozen=True, slots=True)
class RathLLMSettings:
    """Values used to construct ``openai.OpenAI`` and default chat ``model``."""

    api_key: str
    base_url: str | None = None
    default_model: str | None = None


def load_rath_llm_settings(dotenv_path: Path | None = None) -> RathLLMSettings:
    """Load ``OPENAI_*`` from ``.env`` (if present) then read environment.

    Existing environment variables are not overwritten by ``.env``
    (``load_dotenv(..., override=False)``).
    """
    path = dotenv_path if dotenv_path is not None else rath_llm_default_dotenv_path()
    load_dotenv_if_present(path, override=False)

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    base_raw = os.environ.get("OPENAI_BASE_URL", "").strip()
    model_raw = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip()

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is empty: set it in .env or the environment",
        )

    return RathLLMSettings(
        api_key=api_key,
        base_url=base_raw or None,
        default_model=model_raw or None,
    )
