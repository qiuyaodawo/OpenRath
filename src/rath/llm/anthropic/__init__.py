"""Anthropic adapter for :class:`rath.llm.ChatClient`.

Imports of this subpackage auto-register
:class:`~rath.llm.anthropic.client.RathAnthropicChatClient` under
``provider_kind="anthropic"``.
"""

from __future__ import annotations

from rath.llm.anthropic.client import ANTHROPIC_RETRYABLE, RathAnthropicChatClient
from rath.llm.anthropic.create_kwargs import build_anthropic_kwargs
from rath.llm.anthropic.normalize import normalize_anthropic_response
from rath.llm.registry import register_chat_client

register_chat_client("anthropic", RathAnthropicChatClient)

__all__ = [
    "RathAnthropicChatClient",
    "ANTHROPIC_RETRYABLE",
    "build_anthropic_kwargs",
    "normalize_anthropic_response",
]
