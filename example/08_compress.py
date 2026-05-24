"""08 · Compression — shrink a session's context with `flow.Compressor`.

As a session accumulates turns, its chunk table grows. `flow.Compressor` is a
`Workflow` that runs `run_session_compress`: it replaces the transcript with a
shorter summary while preserving the thread, so later turns stay cheap. This
example builds a little history, compresses it, and reports the chunk-count
before and after.

Run:
    python example/08_compress.py

Needs an OpenAI-compatible key (see ``_shared/provider.py``).
"""

from __future__ import annotations

from _shared import provider_from_env, stream_to_stdout

from rath import flow
from rath.session import Session


def main() -> None:
    provider = provider_from_env()
    agent = flow.Agent(
        "You are a verbose assistant; answer in a full paragraph.",
        provider,
        on_event=stream_to_stdout(),
    )

    session = Session.from_user_message(
        "Explain what a sandbox backend is in OpenRath, with an analogy."
    ).to("local")
    session = agent(session)
    print()

    before = len(session.chunk_table.rows)
    print(f"\n--- chunks before compression: {before}")

    compressor = flow.Compressor(
        "Summarize the conversation so far into a single concise assistant "
        "message that preserves the key facts. Drop redundancy.",
        provider,
        on_event=stream_to_stdout(),
    )
    session = compressor.forward(session)
    print()

    after = len(session.chunk_table.rows)
    print(f"\n--- chunks after compression: {after}")


if __name__ == "__main__":
    main()
