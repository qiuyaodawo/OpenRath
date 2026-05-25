"""Chat-client Protocols consumed by the session loop.

Two runtime-checkable Protocols define the contract every LLM adapter must
satisfy:

* :class:`ChatClient` — the minimum surface (``provider`` + blocking
  ``complete``). Sufficient for :class:`~rath.session.loop.run_session_loop`.
* :class:`StreamingChatClient` — extends :class:`ChatClient` with
  ``complete_stream``. :func:`~rath.session.loop.run_session_loop` switches to
  streaming when ``on_event`` is supplied and guards on this Protocol instead
  of inspecting :attr:`~rath.llm.Provider.provider_kind`, so any adapter that
  implements ``complete_stream`` gains streaming support automatically.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from rath.llm.chat_request import RathLLMChatRequest
from rath.llm.chat_response import RathLLMChatResponse, RathLLMStreamDelta
from rath.llm.provider import Provider

__all__ = ["ChatClient", "StreamingChatClient"]


@runtime_checkable
class ChatClient(Protocol):
    """Minimal synchronous chat-completion contract.

    Implementations must keep ``complete`` blocking and side-effect-free
    beyond the network call itself; retries / token accounting / budget
    handling are layered above in the session loop.
    """

    @property
    def provider(self) -> Provider: ...

    def complete(self, req: RathLLMChatRequest) -> RathLLMChatResponse: ...


@runtime_checkable
class StreamingChatClient(ChatClient, Protocol):
    """A :class:`ChatClient` that also supports streaming completions.

    :func:`~rath.session.loop.run_session_loop` accepts any object satisfying
    this Protocol when ``on_event`` is provided. Both OpenAI and Anthropic
    adapters implement it.
    """

    def complete_stream(
        self, req: RathLLMChatRequest
    ) -> Iterator[RathLLMStreamDelta]: ...
