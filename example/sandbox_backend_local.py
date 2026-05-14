"""Example: session loop with the local subprocess sandbox (LLM keys as needed)."""

from dataclasses import replace

from _chunk_print import example_chunk_print
from _openai_provider import provider_from_env

import rath.backend as backend
import rath.flow as flow
from rath.session import Session

SANDBOX_BACKEND = "local"

_PROVIDER = replace(provider_from_env(), model="glm-5.1")

agent = flow.Agent(
    system_prompt="You are a helpful assistant.",
    provider=_PROVIDER,
    chunk_print=example_chunk_print(),
)


def main() -> None:
    user_session = Session.from_user_message(
        "List all files in the current directory. And summarize the result."
    )
    print(user_session.sandbox_backend)

    # Ephemeral workspace (no host working directory).
    user_session = user_session.to(SANDBOX_BACKEND, spec=None)
    agent(user_session)

    # Repository root bound as the sandbox working directory.
    user_session = user_session.to(SANDBOX_BACKEND, spec=".")
    agent(user_session)


if __name__ == "__main__":
    if backend.get(SANDBOX_BACKEND).is_available():
        main()
    else:
        print(f"Sandbox backend {SANDBOX_BACKEND} is not available.")
