"""Example: session loop with OpenSandbox (API server, Docker, LLM keys as needed)."""

from dataclasses import replace

from _on_event import example_on_event
from _openai_provider import provider_from_env

import rath.backend as backend
import rath.flow as flow
from rath.session import Session

SANDBOX_BACKEND = "opensandbox"

_PROVIDER = replace(provider_from_env(), model="glm-5.1")

agent = flow.Agent(
    system_prompt="You are a helpful assistant.",
    provider=_PROVIDER,
    on_event=example_on_event(),
)


def main() -> None:
    user_session = Session.from_user_message(
        "List all files in the current directory. And summarize the result."
    )
    print(user_session.sandbox_backend)

    # Ephemeral in-container workspace (no host volume bind).
    user_session = user_session.to(SANDBOX_BACKEND, spec=None)
    agent(user_session)

    # Host project directory bound into the sandbox workspace.
    user_session = user_session.to(SANDBOX_BACKEND, spec=".")
    agent(user_session)


if __name__ == "__main__":
    if backend.get(SANDBOX_BACKEND).is_available():
        main()
    else:
        print(f"Sandbox backend {SANDBOX_BACKEND} is not available.")
