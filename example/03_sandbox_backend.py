"""03 · Sandbox backend — `.to(...)` is OpenRath's `tensor.to(device)`.

A session declares *where* its tools run by binding a sandbox backend. The
``spec`` controls the working directory:

- ``spec=None`` — an ephemeral workspace with no host directory.
- ``spec="."`` — bind a host path as the sandbox working directory.

The same agent code runs unchanged on either backend; only the string passed
to ``.to(...)`` changes. Pass a backend name as the first argument to switch:

    python example/03_sandbox_backend.py             # local (default)
    python example/03_sandbox_backend.py opensandbox  # needs an OpenSandbox stack

Needs an OpenAI-compatible key (see ``_shared/provider.py``).
"""

from __future__ import annotations

import sys

from _shared import provider_from_env, stream_to_stdout

import rath.backend as backend
from rath import flow
from rath.session import Session


def run_on(backend_name: str) -> None:
    agent = flow.Agent(
        "You are a helpful assistant. Built-in filesystem tools are available.",
        provider_from_env(),
        on_event=stream_to_stdout(),
    )

    print(f"=== {backend_name}: ephemeral workspace (spec=None) ===")
    ephemeral = Session.from_user_message(
        "List the files in the current directory, then summarize what you found."
    ).to(backend_name, spec=None)
    agent(ephemeral)
    print()

    print(f"\n=== {backend_name}: host directory bound (spec='.') ===")
    bound = Session.from_user_message(
        "List the files in the current directory, then summarize what you found."
    ).to(backend_name, spec=".")
    agent(bound)
    print()


def main() -> None:
    backend_name = sys.argv[1] if len(sys.argv) > 1 else "local"
    if not backend.get(backend_name).is_available():
        print(f"Sandbox backend {backend_name!r} is not available.")
        return
    run_on(backend_name)


if __name__ == "__main__":
    main()
