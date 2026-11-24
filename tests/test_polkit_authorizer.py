"""PolkitAuthorizer error handling with a fake bus connection (no polkit needed)."""

from __future__ import annotations

import logging
from typing import Any

import pytest

pytest.importorskip("gi")

from gi.repository import GLib  # noqa: E402

from avell_keyboard_rgb.dbus_service import PolkitAuthorizer  # noqa: E402

TRUSTED = (
    "Only trusted callers (e.g. uid 0 or an action owner) can use CheckAuthorization() "
    "for subjects belonging to other identities"
)


class FailingConnection:
    def __init__(self, message: str) -> None:
        self.message = message

    def call(self, *args: Any) -> None:
        args[-1](self, object())

    def call_finish(self, _result: object) -> Any:
        raise GLib.Error(self.message)


def run_check(message: str) -> list[bool]:
    seen: list[bool] = []
    PolkitAuthorizer().check(FailingConnection(message), ":1.5", seen.append)
    return seen


def test_polkit_error_denies_and_points_at_owner_annotation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR):
        assert run_check(TRUSTED) == [False]
    assert "polkit check failed" in caplog.text
    assert "org.freedesktop.policykit.owner" in caplog.text


def test_other_polkit_error_denies_without_hint(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        assert run_check("boom") == [False]
    assert "policykit.owner" not in caplog.text
