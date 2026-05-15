"""Unit tests for :func:`rath.llm.credentials.resolve_credential`."""

from __future__ import annotations

from rath.llm.credentials import resolve_credential


def test_first_non_empty_wins() -> None:
    assert resolve_credential("alpha", "beta") == "alpha"


def test_skips_none() -> None:
    assert resolve_credential(None, "beta") == "beta"


def test_skips_empty_and_whitespace() -> None:
    assert resolve_credential("", "  ", "gamma") == "gamma"


def test_strips_winning_value() -> None:
    assert resolve_credential("  hello  ") == "hello"


def test_all_empty_returns_empty_string() -> None:
    assert resolve_credential(None, "", "   ") == ""


def test_no_candidates_returns_empty_string() -> None:
    assert resolve_credential() == ""
