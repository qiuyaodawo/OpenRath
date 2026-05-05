"""Load .env before session checks; fail fast if credentials are missing."""

from __future__ import annotations

import os

import pytest

from rath.utils.env import default_env_file_path, load_dotenv_if_present


def pytest_configure(config: pytest.Config) -> None:
    # Real integration tests: load local .env without overriding exported env vars.
    load_dotenv_if_present(default_env_file_path(), override=False)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        pytest.exit(
            "OPENAI_API_KEY must be set (e.g. in .env) for tests/llm; "
            "these tests call the live API — no mocks.",
            returncode=2,
        )
