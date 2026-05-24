"""09 · Memory — the ergonomic `flow.Agent` memory API.

`flow.Agent(memory="local")` binds a memory store to the agent and exposes
`remember()` / `recall()` / `commit()`. The local backend ships with the base
install and needs no API key: `recall` falls back to BM25 lexical search when
no embedding client is configured. (Set ``OPENAI_API_KEY`` to enable embedding
rank and the optional final commit-after-a-turn step.)

Run:
    python example/09_memory.py

Runs without any key; an LLM key only unlocks the optional live turn at the end.
"""

from __future__ import annotations

from _shared.provider import has_credentials, provider_from_env

from rath import flow
from rath.session import Session


def build_agent() -> flow.Agent:
    """A real provider when a key is present; a placeholder model otherwise.

    remember/recall never call the LLM, so a bare ``model="demo"`` is enough to
    satisfy the constructor when no credentials are configured.
    """
    if has_credentials():
        return flow.Agent("You are a concise assistant.", provider_from_env(), memory="local")
    return flow.Agent("You are a concise assistant.", model="demo", memory="local")


def main() -> None:
    with build_agent() as agent:
        agent.remember("The user prefers a dark colour theme at night.")
        agent.remember("The user reads English and writes Python.")
        print("[ok] wrote two preference notes")

        found = agent.recall("reading code at night", top_k=3)
        print(f"[ok] recall returned {len(found.hits)} hit(s):")
        for hit in found.hits:
            print(f"      {hit.score:6.3f}  {hit.uri}")

        if not has_credentials():
            print("[note] no LLM key — skipping the optional live turn + commit")
            return

        out = agent(Session.from_user_message("Say hello in one word.").to("local"))
        agent.commit(out)
        print("[ok] committed the turn transcript into memory")


if __name__ == "__main__":
    main()
