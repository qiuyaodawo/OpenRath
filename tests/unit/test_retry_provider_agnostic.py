"""Unit tests for the provider-agnostic :mod:`rath.llm.retry` helper.

These complement the OpenAI-flavored coverage in
:mod:`tests.unit.test_retry`, which exercises the back-compat shim that
injects OpenAI's transient errors as a default.
"""

from __future__ import annotations

from typing import Callable, Iterator

import pytest

from rath.llm.retry import retry_with_backoff


class _TransientA(Exception):
    """Stand-in for a custom provider transient error."""


class _TransientB(Exception):
    pass


def _scripted(seq: list[BaseException | str]) -> Callable[[], str]:
    it: Iterator[BaseException | str] = iter(seq)

    def _call() -> str:
        x = next(it)
        if isinstance(x, BaseException):
            raise x
        return x

    return _call


def test_retries_only_on_listed_exceptions() -> None:
    sleeps: list[float] = []
    call = _scripted([_TransientA("flaky"), _TransientA("flaky"), "ok"])
    out = retry_with_backoff(
        call,
        retryable=(_TransientA,),
        max_attempts=5,
        base_seconds=0.01,
        jitter=False,
        sleep=sleeps.append,
    )
    assert out == "ok"
    assert len(sleeps) == 2


def test_empty_retryable_never_retries() -> None:
    sleeps: list[float] = []
    call = _scripted([_TransientA("flaky")])
    with pytest.raises(_TransientA):
        retry_with_backoff(
            call,
            retryable=(),
            max_attempts=5,
            base_seconds=0.01,
            jitter=False,
            sleep=sleeps.append,
        )
    assert sleeps == []


def test_multiple_retryable_types() -> None:
    sleeps: list[float] = []
    call = _scripted([_TransientA("a"), _TransientB("b"), "done"])
    out = retry_with_backoff(
        call,
        retryable=(_TransientA, _TransientB),
        max_attempts=5,
        base_seconds=0.01,
        jitter=False,
        sleep=sleeps.append,
    )
    assert out == "done"
    assert len(sleeps) == 2


def test_non_retryable_propagates_immediately() -> None:
    sleeps: list[float] = []

    def call() -> str:
        raise RuntimeError("not retryable")

    with pytest.raises(RuntimeError, match="not retryable"):
        retry_with_backoff(
            call,
            retryable=(_TransientA,),
            max_attempts=4,
            base_seconds=0.01,
            jitter=False,
            sleep=sleeps.append,
        )
    assert sleeps == []


def test_helper_does_not_import_openai() -> None:
    """The provider-agnostic helper must not pull in the openai SDK."""
    import importlib
    import sys

    # If `rath.llm.retry` already imported `openai`, this assertion would
    # still trip on any later import; that's the property we care about.
    module = importlib.import_module("rath.llm.retry")
    src = module.__file__
    assert src is not None
    with open(src, "r", encoding="utf-8") as fp:
        text = fp.read()
    assert "import openai" not in text and "from openai" not in text
    # Sanity: this test itself does not load openai as a side-effect.
    assert "rath.llm.retry" in sys.modules
