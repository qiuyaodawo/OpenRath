"""Internal: exponential-backoff retry for transient OpenAI-compatible errors.

Lives under ``_retry`` (single leading underscore) because it is an
implementation detail of :class:`~rath.llm.client.RathOpenAIChatClient`. Not
exported from :mod:`rath.llm`.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_BASE_SECONDS = 0.5
DEFAULT_CAP_SECONDS = 30.0

_RETRYABLE: tuple[type[BaseException], ...] = (
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
)


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    max_attempts: int | None = None,
    base_seconds: float | None = None,
    cap_seconds: float = DEFAULT_CAP_SECONDS,
    jitter: bool = True,
    sleep: Callable[[float], None] = time.sleep,
    extra_retryable: tuple[type[BaseException], ...] = (),
) -> T:
    """Call ``fn`` with exponential backoff on transient API errors.

    Retries on :class:`openai.RateLimitError`, :class:`openai.APIConnectionError`,
    :class:`openai.APITimeoutError`, and :class:`openai.InternalServerError`. All
    other exceptions propagate immediately. Pass ``extra_retryable`` (a tuple of
    exception classes) to widen the retryable set for non-OpenAI clients - the
    Anthropic adapter, for example, supplies ``anthropic.*`` siblings of the
    same transient categories.

    Backoff: ``base * 2**(attempt-1)`` capped at ``cap_seconds``, plus optional
    uniform jitter in ``[0, base)``.

    ``sleep`` is parameterized so tests can run without real wall-clock waits.
    """
    attempts = max_attempts if max_attempts is not None else DEFAULT_MAX_ATTEMPTS
    base = base_seconds if base_seconds is not None else DEFAULT_BASE_SECONDS
    if attempts < 1:
        attempts = 1
    retryable: tuple[type[BaseException], ...] = _RETRYABLE + tuple(extra_retryable)

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
