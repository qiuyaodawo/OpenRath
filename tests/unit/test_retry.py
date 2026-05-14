"""Unit tests for :mod:`rath.llm._retry`."""

from __future__ import annotations

from typing import Callable, Iterator

import httpx
import pytest
from openai import APIConnectionError, RateLimitError

from rath.llm._retry import retry_with_backoff


def _fake_rate_limit() -> RateLimitError:
    """Build a RateLimitError without going through the OpenAI SDK constructor.

    The SDK's exception classes accept ``message``/``response``/``body`` so we
    construct a minimal response. Older / newer SDK versions accept slightly
    different shapes - this signature is stable across openai 1.x.
    """
    resp = httpx.Response(429, request=httpx.Request("POST", "https://x"))
    return RateLimitError(message="rate limited", response=resp, body=None)


def _fake_connection_error() -> APIConnectionError:
    return APIConnectionError(request=httpx.Request("POST", "https://x"))


def _scripted(seq: list[BaseException | str]) -> Callable[[], str]:
    """Build a thunk that yields the next exception-or-value on each call."""
    it: Iterator[BaseException | str] = iter(seq)

    def _call() -> str:
        x = next(it)
        if isinstance(x, BaseException):
            raise x
        return x

    return _call


def test_retries_on_rate_limit_and_eventually_succeeds() -> None:
    sleeps: list[float] = []
    call = _scripted([_fake_rate_limit(), _fake_rate_limit(), "ok"])
    result = retry_with_backoff(
        call,
        max_attempts=5,
        base_seconds=0.01,
        jitter=False,
        sleep=sleeps.append,
    )
    assert result == "ok"
    assert len(sleeps) == 2  # two backoffs before the third successful attempt


def test_retries_on_api_connection_error() -> None:
    call = _scripted([_fake_connection_error(), "recovered"])
    sleeps: list[float] = []
    out = retry_with_backoff(
        call,
        max_attempts=3,
        base_seconds=0.01,
        jitter=False,
        sleep=sleeps.append,
    )
    assert out == "recovered"


def test_gives_up_after_max_attempts() -> None:
    sleeps: list[float] = []
    call = _scripted([_fake_rate_limit(), _fake_rate_limit(), _fake_rate_limit()])
    with pytest.raises(RateLimitError):
        retry_with_backoff(
            call,
            max_attempts=3,
            base_seconds=0.01,
            jitter=False,
            sleep=sleeps.append,
        )
    # 3 attempts means 2 backoffs (no sleep after the final failure).
    assert len(sleeps) == 2


def test_non_retryable_propagates_immediately() -> None:
    sleeps: list[float] = []

    def call() -> str:
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        retry_with_backoff(
            call,
            max_attempts=4,
            base_seconds=0.01,
            jitter=False,
            sleep=sleeps.append,
        )
    assert sleeps == []  # never slept; not retryable


def test_backoff_grows_exponentially() -> None:
    sleeps: list[float] = []
    call = _scripted([_fake_rate_limit(), _fake_rate_limit(), _fake_rate_limit(), "ok"])
    retry_with_backoff(
        call,
        max_attempts=4,
        base_seconds=0.1,
        jitter=False,
        sleep=sleeps.append,
    )
    # No jitter: 0.1, 0.2, 0.4
    assert sleeps == [pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.4)]


class _CustomTransient(Exception):
    """Stand-in for a non-OpenAI transient exception (e.g. anthropic.*)."""


def test_extra_retryable_widens_the_set() -> None:
    sleeps: list[float] = []
    call = _scripted([_CustomTransient("flaky"), "ok"])
    out = retry_with_backoff(
        call,
        max_attempts=3,
        base_seconds=0.01,
        jitter=False,
        sleep=sleeps.append,
        extra_retryable=(_CustomTransient,),
    )
    assert out == "ok"
    assert len(sleeps) == 1


def test_extra_retryable_default_empty_does_not_catch_custom() -> None:
    sleeps: list[float] = []
    call = _scripted([_CustomTransient("flaky"), "ok"])
    with pytest.raises(_CustomTransient):
        retry_with_backoff(
            call,
            max_attempts=3,
            base_seconds=0.01,
            jitter=False,
            sleep=sleeps.append,
        )
    assert sleeps == []
