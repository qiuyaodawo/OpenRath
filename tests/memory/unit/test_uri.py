"""Tests for :mod:`rath.memory.uri`."""

from __future__ import annotations

from rath.memory.uri import (
    MEMORY_URI_PREFIX,
    to_public_uri,
    to_wire_uri,
    valid_memory_uri,
)


def test_valid_memory_uri_accepts_public_and_legacy_schemes() -> None:
    assert valid_memory_uri("memory://user/memories/x")
    assert valid_memory_uri("memory://user/memories/x")
    assert valid_memory_uri("memory:/")
    assert not valid_memory_uri("file:///tmp/x")
    assert not valid_memory_uri("memory://bogus/x")


def test_to_wire_and_public_round_trip() -> None:
    public = "memory://user/memories/preferences/dark"
    wire = "viking://user/memories/preferences/dark"
    assert to_wire_uri(public) == wire
    assert to_public_uri(wire) == public
    assert to_public_uri(to_wire_uri("memory:/")) == "memory:/"


def test_public_prefix_constant() -> None:
    assert MEMORY_URI_PREFIX == "memory://"
