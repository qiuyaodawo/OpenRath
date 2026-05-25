"""Memory URI scheme helpers.

OpenRath's public URI scheme is ``memory://``. The OpenViking SDK still
speaks ``viking://`` on the wire; :mod:`rath.memory.adapters.openviking`
translates at the adapter boundary via :func:`to_wire_uri` /
:func:`to_public_uri`.
"""

from __future__ import annotations

MEMORY_URI_PREFIX = "memory://"
LEGACY_MEMORY_URI_PREFIX = "viking://"
MEMORY_URI_ROOT = "memory:/"
LEGACY_MEMORY_URI_ROOT = "viking:/"

_VALID_SCOPES: frozenset[str] = frozenset({"user", "agent", "session", "resources"})

__all__ = [
    "MEMORY_URI_PREFIX",
    "LEGACY_MEMORY_URI_PREFIX",
    "MEMORY_URI_ROOT",
    "is_memory_uri",
    "valid_memory_uri",
    "to_public_uri",
    "to_wire_uri",
    "memory_uri_prefix",
]


def memory_uri_prefix(uri: str) -> str | None:
    """Return the scheme prefix when ``uri`` is a memory URI, else ``None``."""
    for prefix in (MEMORY_URI_PREFIX, LEGACY_MEMORY_URI_PREFIX):
        if uri.startswith(prefix):
            return prefix
    if uri.rstrip("/") in (
        MEMORY_URI_ROOT.rstrip("/"),
        LEGACY_MEMORY_URI_ROOT.rstrip("/"),
    ):
        return MEMORY_URI_ROOT
    return None


def is_memory_uri(uri: str) -> bool:
    """Return ``True`` when ``uri`` uses ``memory://`` or legacy ``viking://``."""
    return memory_uri_prefix(uri) is not None


def valid_memory_uri(uri: str) -> bool:
    """Return ``True`` when ``uri`` has a known memory scope prefix."""
    prefix = memory_uri_prefix(uri)
    if prefix is None:
        return False
    if uri.rstrip("/") in (
        MEMORY_URI_ROOT.rstrip("/"),
        LEGACY_MEMORY_URI_ROOT.rstrip("/"),
    ):
        return True
    scheme = (
        MEMORY_URI_PREFIX
        if uri.startswith(MEMORY_URI_PREFIX)
        else LEGACY_MEMORY_URI_PREFIX
    )
    tail = uri[len(scheme) :]
    if not tail:
        return False
    head = tail.split("/", 1)[0]
    return head in _VALID_SCOPES


def to_public_uri(uri: str) -> str:
    """Map wire / legacy ``viking://`` URIs to the public ``memory://`` form."""
    if uri.rstrip("/") == LEGACY_MEMORY_URI_ROOT.rstrip("/"):
        return MEMORY_URI_ROOT
    if uri.startswith(LEGACY_MEMORY_URI_PREFIX):
        return MEMORY_URI_PREFIX + uri[len(LEGACY_MEMORY_URI_PREFIX) :]
    return uri


def to_wire_uri(uri: str) -> str:
    """Map public ``memory://`` URIs to OpenViking's ``viking://`` wire form."""
    if uri.rstrip("/") == MEMORY_URI_ROOT.rstrip("/"):
        return LEGACY_MEMORY_URI_ROOT
    if uri.startswith(MEMORY_URI_PREFIX):
        return LEGACY_MEMORY_URI_PREFIX + uri[len(MEMORY_URI_PREFIX) :]
    return uri
