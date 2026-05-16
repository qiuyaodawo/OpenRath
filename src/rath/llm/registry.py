"""Registry mapping :attr:`Provider.provider_kind` to a :class:`ChatClient` factory.

Built-in adapters (``"openai"``, ``"anthropic"``) self-register on import of
:mod:`rath.llm.openai` / :mod:`rath.llm.anthropic`, which :mod:`rath.llm` does
eagerly. Third parties can call :func:`register_chat_client` to add their own
without modifying core.

The single dispatch point :func:`chat_client_for` replaces the previous
``provider.provider_kind == "anthropic"`` string check that lived in
:mod:`rath.session.loop`.
"""

from __future__ import annotations

from typing import Callable

from rath.llm.base import ChatClient
from rath.llm.provider import Provider

__all__ = [
    "ChatClientFactory",
    "register_chat_client",
    "chat_client_for",
    "registered_kinds",
]

ChatClientFactory = Callable[[Provider], ChatClient]

_FACTORIES: dict[str, ChatClientFactory] = {}


def register_chat_client(kind: str, factory: ChatClientFactory) -> None:
    """Register ``factory(provider) -> ChatClient`` under ``kind``.

    Overwrites any previous registration silently — late imports therefore
    win. Built-in kinds (``"openai"``, ``"anthropic"``) are registered when
    their subpackages are imported by :mod:`rath.llm`.
    """
    _FACTORIES[kind] = factory


def chat_client_for(provider: Provider) -> ChatClient:
    """Return the :class:`ChatClient` for ``provider.provider_kind``.

    ``provider.provider_kind=None`` defaults to ``"openai"``. Unknown kinds
    raise ``ValueError`` listing what is currently registered.
    """
    kind = provider.provider_kind or "openai"
    try:
        factory = _FACTORIES[kind]
    except KeyError as e:
        raise ValueError(
            f"unknown provider_kind={kind!r}; registered kinds: {sorted(_FACTORIES)}",
        ) from e
    return factory(provider)


def registered_kinds() -> tuple[str, ...]:
    """Snapshot of currently registered kinds (useful for diagnostics / tests)."""
    return tuple(sorted(_FACTORIES))
