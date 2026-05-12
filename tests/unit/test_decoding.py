"""Tests for :mod:`rath.utils.decoding`."""

from __future__ import annotations

import pytest

from rath.utils.decoding import decode_subprocess_output


def test_decode_empty() -> None:
    assert decode_subprocess_output(b"") == ""


def test_decode_plain_utf8() -> None:
    assert decode_subprocess_output(b"hello") == "hello"
    assert decode_subprocess_output("测试".encode("utf-8")) == "测试"


def test_decode_prefers_valid_utf8_over_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rath.utils.decoding.locale.getpreferredencoding", lambda _: "ascii"
    )
    assert decode_subprocess_output("café".encode("utf-8")) == "café"


def test_decode_falls_back_to_preferred_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "rath.utils.decoding.locale.getpreferredencoding", lambda _: "gbk"
    )
    assert decode_subprocess_output("卷".encode("gbk")) == "卷"
