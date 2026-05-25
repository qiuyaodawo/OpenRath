"""Provider-agnostic exponential-backoff retry helper.

This module knows nothing about vendor-specific exception classes — each
:class:`ChatClient` adapter passes its own ``retryable`` tuple. Legacy callers
that imported OpenAI defaults from a removed shim should use
:data:`rath.llm.openai.OPENAI_RETRYABLE` instead.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_SECONDS = 0.5
DEFAULT_CAP_SECONDS = 30.0

__all__ = [
    "retry_with_backoff",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BASE_SECONDS",
    "DEFAULT_CAP_SECONDS",
]


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    retryable: tuple[type[BaseException], ...],
    max_attempts: int | None = None,
    base_seconds: float | None = None,
    cap_seconds: float = DEFAULT_CAP_SECONDS,
    jitter: bool = True,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` with exponential backoff on exceptions matching ``retryable``.

    ``retryable`` is required and provider-specific — adapters pass e.g.
    ``(openai.RateLimitError, openai.APIConnectionError, ...)``. Empty tuple
    disables retry. Backoff is ``base * 2**(attempt-1)`` capped at
    ``cap_seconds``, plus optional uniform jitter in ``[0, base)``.

    ``sleep`` is parameterized so tests can run without real wall-clock waits.
    """
    attempts = max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS
    base = base_seconds if base_seconds is not None else DEFAULT_BASE_SECONDS
    if attempts < 1:
        attempts = 1

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except retryable as exc:
            last_exc = exc
            if attempt >= attempts:
                break
            delay = min(cap_seconds, base * (2 ** (attempt - 1)))
            if jitter:
                delay += random.uniform(0.0, base)
            logger.warning(
                "retry_with_backoff: %s on attempt %d/%d; sleeping %.2fs",
                type(exc).__name__,
                attempt,
                attempts,
                delay,
            )
            sleep(delay)
    assert last_exc is not None
    raise last_exc
