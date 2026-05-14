"""Drive a session loop through the Anthropic adapter.

Set ``ANTHROPIC_API_KEY`` in the environment (or in a project ``.env``).

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
from rath.llm import Provider
from rath.session import Session


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set; export it or add to .env",
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
