"""04 · Built-in tools — the kernels the sandbox already exposes.

A tool is OpenRath's `kernel/op`: the smallest callable surface the backend
runs. `run_session_loop` (and therefore `flow.Agent`) always merges the
built-in system tools into every loop, so an agent can read, write, and
execute inside its sandbox with **no extra wiring**. This example exercises
them end to end: write a file, read it back, and run a shell command.

Run:
    python example/04_tools_builtin.py

Needs an OpenAI-compatible key (see ``_shared/provider.py``).
"""

from __future__ import annotations

from _shared import provider_from_env, stream_to_stdout

from rath import flow
from rath.flow.tool import global_system_tools
from rath.session import Session


def main() -> None:
    print("built-in tools available to every loop:")
    for name in sorted(global_system_tools()):
        print(f"  - {name}")
    print()

    agent = flow.Agent(
        "You are a file-savvy assistant. Use the built-in tools to do real "
        "filesystem and shell work, then report what you did.",
        provider_from_env(),
        on_event=stream_to_stdout(),
    )

    user = Session.from_user_message(
        "Write 'hello from openrath' to notes.txt, read it back to confirm, "
        "then run a shell command that prints the line count of notes.txt. "
        "Summarize the results in one sentence."
    ).to("local", spec=".")

    agent(user)
    print()


if __name__ == "__main__":
    main()
