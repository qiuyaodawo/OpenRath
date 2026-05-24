"""01 · Hello, Agent — the smallest OpenRath program.

`flow.Agent` is OpenRath's `nn.Module`: build it once with a system prompt and
a provider, then *call* it on a `Session` (the "tensor") to get an updated
session back. This is the canonical entry point — most examples build on it.

Run:
    python example/01_hello_agent.py

Needs an OpenAI-compatible key: export ``OPENAI_API_KEY`` (and optionally
``OPENAI_BASE_URL`` / ``OPENAI_DEFAULT_MODEL``), or configure
``llm.default_provider`` in ``~/.openrath/config.json``.
"""

from __future__ import annotations

from _shared import provider_from_env, stream_to_stdout

from rath import flow
from rath.session import Session


def main() -> None:
    agent = flow.Agent(
        "You are a concise assistant.",
        provider_from_env(),
        on_event=stream_to_stdout(),
    )

    user = Session.from_user_message("In one sentence, what is OpenRath?").to("local")
    out = agent(user)
    print()  # newline after the streamed answer

    if out.cumulative_usage is not None:
        print(f"--- tokens: total={out.cumulative_usage.total_tokens}")


if __name__ == "__main__":
    main()
