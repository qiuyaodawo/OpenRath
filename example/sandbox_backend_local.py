"""Example: session loop with the local subprocess sandbox (LLM keys as needed)."""

from dataclasses import replace

import rath.flow as flow
import rath.backend as backend
from rath.session import Session

from _openai_provider import provider_from_env
from _chunk_print import example_chunk_print


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

    # No working directory: ephemeral empty workspace.
    user_session = user_session.to(SANDBOX_BACKEND, spec=None)
    out_session = agent(user_session)
    print(out_session.chunk_table.rows[-1].payload["content"])

    # Project root on the host.
    user_session = user_session.to(SANDBOX_BACKEND, spec=".")
    out_session = agent(user_session)
    print(out_session.chunk_table.rows[-1].payload["content"])


if __name__ == "__main__":
    if backend.get(SANDBOX_BACKEND).is_available():
        main()
    else:
        print(f"Sandbox backend {SANDBOX_BACKEND} is not available.")
