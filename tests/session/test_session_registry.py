"""Tests for :class:`~rath.session.manager.SessionRegistry`."""

from __future__ import annotations

from rath.session import Session, session_registry


def test_session_registry_active_roundtrip() -> None:
    reg = session_registry()
    reg.set_active(None)

    s = Session.user_message("registry probe")
    reg.register(s)
    reg.set_active(s)
    assert reg.get_active_id() == s.id

    reg.set_active(None)
    assert reg.get_active_id() is None
