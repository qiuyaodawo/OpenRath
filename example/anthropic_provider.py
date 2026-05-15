"""Drive a session loop through the Anthropic adapter.

Set ``ANTHROPIC_API_KEY`` in the environment, or define
``llm.default_provider`` (with an Anthropic entry) in
``~/.openrath/config.json``.

Run::

    python example/anthropic_provider.py

The only difference from the OpenAI flow is ``provider_kind="anthropic"`` on
the :class:`Provider`; the rest of the OpenRath surface (Agent, Session,
run_session_loop) is unchanged.
"""

from __future__ import annotations

import os
import sys

from rath import flow
from rath.config.store import ConfigStore
from rath.llm import Provider
from rath.session import Session


def _has_anthropic_credentials() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return True
    try:
        store = ConfigStore.load()
    except (FileNotFoundError, RuntimeError):
        return False
    default = store.config.llm.default_provider
    if default is None:
        return False
    entry = store.config.llm.providers.get(default)
    return bool(entry and entry.api_key)


def main() -> None:
    if not _has_anthropic_credentials():
        print(
            "Anthropic credentials not found: export ANTHROPIC_API_KEY or "
            "configure llm.default_provider with an api_key in "
            "~/.openrath/config.json.",
            file=sys.stderr,
        )
        sys.exit(1)

    agent = flow.Agent(
        "You are a concise assistant.",
        Provider(
            provider_kind="anthropic",
            model="claude-opus-4-7",
            max_tokens=256,
        ),
    )

    user = Session.from_user_message("In one sentence: what is OpenRath?").to("local")
    out = agent(user)

    print("--- transcript ---")
    print(out)
    if out.cumulative_usage is not None:
        print(
            f"--- usage: prompt={out.cumulative_usage.prompt_tokens} "
            f"completion={out.cumulative_usage.completion_tokens} "
            f"total={out.cumulative_usage.total_tokens}"
        )


if __name__ == "__main__":
    main()
