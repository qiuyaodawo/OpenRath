"""10 · Provider variation — same agent code, different backend LLM.

The `Provider` is the only thing that changes when you switch LLM vendors.
The default is OpenAI-compatible; set ``provider_kind="anthropic"`` to route
the same `flow.Agent` through the Anthropic adapter. Everything else — the
Session, the loop, the tools — is identical.

Run:
    python example/10_provider_variation.py             # OpenAI-compatible (default)
    python example/10_provider_variation.py anthropic    # needs ANTHROPIC_API_KEY

OpenAI path needs an OpenAI-compatible key (see ``_shared/provider.py``);
the Anthropic path needs ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import os
import sys

from _shared import provider_from_env, stream_to_stdout

from rath import flow
from rath.llm import Provider
from rath.session import Session


def build_provider(kind: str) -> Provider | None:
    if kind == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            print("ANTHROPIC_API_KEY is not set; cannot run the anthropic variant.")
            return None
        return Provider(
            provider_kind="anthropic",
            model="claude-opus-4-7",
            max_tokens=256,
        )
    try:
        return provider_from_env()
    except ValueError as exc:
        print(exc)
        return None


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else "openai"
    provider = build_provider(kind)
    if provider is None:
        return

    print(f"=== provider_kind={provider.provider_kind or 'openai'} model={provider} ===")
    agent = flow.Agent(
        "You are a concise assistant.",
        provider,
        on_event=stream_to_stdout(),
    )
    agent(Session.from_user_message("In one sentence, what is OpenRath?").to("local"))
    print()


if __name__ == "__main__":
    main()
