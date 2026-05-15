"""OpenAI-compatible adapter for :class:`rath.llm.ChatClient`.

Imports of this subpackage auto-register :class:`RathOpenAIChatClient` under
``provider_kind="openai"`` (and as the default when ``provider_kind`` is
``None``).
"""

from __future__ import annotations

from rath.llm.openai.client import OPENAI_RETRYABLE, RathOpenAIChatClient
from rath.llm.openai.create_kwargs import to_create_kwargs, to_create_kwargs_stream
from rath.llm.openai.normalize import normalize_chat_completion
from rath.llm.registry import register_chat_client

register_chat_client("openai", RathOpenAIChatClient)

__all__ = [
    "RathOpenAIChatClient",
    "OPENAI_RETRYABLE",
    "to_create_kwargs",
    "to_create_kwargs_stream",
    "normalize_chat_completion",
]
