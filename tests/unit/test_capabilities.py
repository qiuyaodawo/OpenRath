"""Tests for :mod:`rath.backend.core.capabilities`."""

from __future__ import annotations

import dataclasses

import pytest

from rath.backend import Capabilities, IsolationLevel


def test_isolation_level_values() -> None:
    assert IsolationLevel.PROCESS.value == "process"
    assert IsolationLevel.CONTAINER.value == "container"
    assert IsolationLevel.MICROVM.value == "microvm"
    assert IsolationLevel.VM.value == "vm"


def test_isolation_level_is_str_enum() -> None:
    """Subclassing ``str`` lets call sites compare against literals if needed."""
    assert IsolationLevel.PROCESS == "process"


def test_capabilities_is_frozen() -> None:
    cap = Capabilities(
        isolation=IsolationLevel.PROCESS,
        supports_command=True,
        supports_filesystem=True,
        supports_code_interpreter=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(cap, "supports_command", False)


def test_capabilities_equality_uses_field_values() -> None:
    a = Capabilities(
        isolation=IsolationLevel.PROCESS,
        supports_command=True,
        supports_filesystem=False,
        supports_code_interpreter=False,
    )
    b = Capabilities(
        isolation=IsolationLevel.PROCESS,
        supports_command=True,
        supports_filesystem=False,
        supports_code_interpreter=False,
    )
    assert a == b
    assert hash(a) == hash(b)


def test_capabilities_optional_fields_default_to_none() -> None:
    cap = Capabilities(
        isolation=IsolationLevel.PROCESS,
        supports_command=True,
        supports_filesystem=True,
        supports_code_interpreter=True,
    )
    assert cap.cold_start_ms_p50 is None
    assert cap.max_sandboxes is None
