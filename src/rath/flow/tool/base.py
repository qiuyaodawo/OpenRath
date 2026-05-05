"""Base type for all flow tool calls dispatched by :class:`~rath.backend.Backend`."""

from __future__ import annotations

__all__ = ["FlowToolCall"]


class FlowToolCall:
    """Marker base for all flow tool call types.

    Concrete subclasses are dataclasses; this base lets
    :meth:`~rath.backend.Backend.supported_calls` return
    ``frozenset[type[FlowToolCall]]`` and keeps pattern matching on a single
    discriminator root.
    """

    __slots__ = ()
