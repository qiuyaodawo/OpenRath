"""Protocol for synchronous chat clients consumed by :class:`DefaultSessionLoopExecutor`.

Anything that exposes a ``provider`` property and a ``complete(request) ->
response`` method satisfies :class:`ChatClient`. The default
:class:`~rath.llm.RathOpenAIChatClient` does already; future adapters (e.g.
Anthropic) only need to match the same shape.

This file is intentionally lightweight - no runtime cost on import, and the
Protocol is :func:`runtime_checkable` so ``isinstance`` works for sanity
checks. Implementation detail: leading underscore in the module name because
the Protocol itself is currently the only public contract callers should
depend on (re-exported via :mod:`rath.llm`).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse
from rath.llm.provider import Provider

__all__ = ["ChatClient"]


@runtime_checkable
class ChatClient(Protocol):
    """Minimal synchronous chat-completion contract.

    Implementations must keep ``complete`` blocking and side-effect-free
    beyond the network call itself; retries / token accounting / budget
    handling are layered above in the session loop.
    """

    @property
    def provider(self) -> Provider:
        ...

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse:
        ...
