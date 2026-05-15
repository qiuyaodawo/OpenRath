"""Tiny credential-resolution helper shared by chat-client adapters.

Both :class:`~rath.llm.openai.client.RathOpenAIChatClient` and
:class:`~rath.llm.anthropic.client.RathAnthropicChatClient` follow the same
pattern: pick the first non-empty value from a precedence-ordered list of
sources (``Provider`` field, then one or more environment variables). This
function centralizes that pattern.
"""

from __future__ import annotations

__all__ = ["resolve_credential"]


def resolve_credential(*candidates: str | None) -> str:
    """Return the first non-empty (after ``strip``) string in ``candidates``.

    Returns an empty string when no candidate qualifies. Callers decide
    whether an empty result is an error.
    """
    for c in candidates:
        if c is None:
            continue
        s = c.strip()
        if s:
            return s
    return ""
