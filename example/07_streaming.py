"""07 · Streaming — watch tokens arrive and read the streamed delta.

Every completion streams `RathLLMStreamDelta` objects to your ``on_event``
callback. ``_shared.stream_to_stdout`` is the convenience version; here we
write the callback by hand to show what a delta carries — incremental content
and a terminal ``finish_reason`` — and then read cumulative token usage off
the returned session.

Run:
    python example/07_streaming.py

Needs an OpenAI-compatible key (see ``_shared/provider.py``).
"""

from __future__ import annotations

import sys

from _shared import provider_from_env

from rath import flow
from rath.llm import RathLLMStreamDelta
from rath.session import Session


def on_event(delta: RathLLMStreamDelta) -> None:
    if delta.content_delta:
        sys.stdout.write(delta.content_delta)
        sys.stdout.flush()
    if delta.finish_reason is not None:
        sys.stdout.write(f"\n[finish_reason={delta.finish_reason}]\n")


def main() -> None:
    agent = flow.Agent(
        "You are a concise assistant.",
        provider_from_env(),
        on_event=on_event,
    )

    user = Session.from_user_message(
        "Count from 1 to 5, with a one-line note about each number."
    ).to("local")
    out = agent(user)

    if out.cumulative_usage is not None:
        print(
            f"--- usage total={out.cumulative_usage.total_tokens} "
            f"(prompt={out.cumulative_usage.prompt_tokens}, "
            f"completion={out.cumulative_usage.completion_tokens})"
        )


if __name__ == "__main__":
    main()
