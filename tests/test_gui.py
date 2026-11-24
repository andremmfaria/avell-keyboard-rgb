"""GUI smoke tests with a fake backend. Skipped when GTK4, libadwaita or a display is missing."""

from __future__ import annotations

from typing import Any

import pytest

gi = pytest.importorskip("gi")
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gdk, GLib, Gtk
except (ValueError, ImportError):
    pytest.skip("GTK4 or libadwaita typelib missing", allow_module_level=True)

Gtk.init_check()
if Gdk.Display.get_default() is None:
    pytest.skip("no display (run under xvfb-run)", allow_module_level=True)

from avell_keyboard_rgb.gui.window import MainWindow  # noqa: E402


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.presence: Any = None
        self.changed: Any = None
        self.state: dict[str, Any] = {
            "device_connected": True,
            "power": True,
            "brightness": 20,
            "zones": ["ff0000", "00ff00", "0000ff", "ffffff"],
            "effect": None,
            "software_effect": "",
        }

    def call_async(self, method: str, params: Any, callback: Any) -> None:
        self.calls.append((method, params.unpack() if params is not None else None))
        if method == "GetState":
            callback((self.state,), None)
        elif method == "ListProfiles":
            callback((["work", "night"],), None)
        else:
            callback(None, None)

    def watch(self, on_presence: Any, on_changed: Any) -> None:
        self.presence, self.changed = on_presence, on_changed


def pump(ms: int = 400) -> None:
    ctx = GLib.MainContext.default()
    loop = GLib.MainLoop()
    GLib.timeout_add(ms, loop.quit)
    loop.run()
    while ctx.pending():
        ctx.iteration(False)


@pytest.fixture
def win() -> tuple[MainWindow, FakeBackend]:
    backend = FakeBackend()
    app = Adw.Application(application_id="io.github.andremmfaria.AvellRgbGuiTest")
    return MainWindow(app, backend), backend


def test_initial_state_loaded(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    assert ("GetState", None) in backend.calls
    assert window._zones == ["ff0000", "00ff00", "0000ff", "ffffff"]
    assert int(window._brightness.get_value()) == 20
    assert len(window._profile_rows) == 2
    assert not window._banner.get_revealed()


def test_banner_follows_daemon_presence(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    backend.presence(False)
    assert window._banner.get_revealed()
    backend.presence(True)
    assert not window._banner.get_revealed()


def test_zone_selection_and_identify(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    window._zone_buttons[2].set_active(True)
    assert window._zone == 3
    window._on_identify(None)  # type: ignore[arg-type]
    assert ("IdentifyZone", (3,)) in backend.calls


def test_brightness_is_debounced_and_sent(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    backend.calls.clear()
    for v in (30, 31, 32):
        window._brightness.set_value(v)
    pump()
    assert [c for c in backend.calls if c[0] == "SetBrightness"] == [("SetBrightness", (32,))]


def test_effect_selection_sends_effect(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    backend.calls.clear()
    window._effect_row.set_selected(2)  # wave
    pump()
    sent = [c for c in backend.calls if c[0] == "SetEffect"]
    assert sent and sent[-1][1][0] == "wave"


def test_state_apply_does_not_echo_back(win: tuple[MainWindow, FakeBackend]) -> None:
    window, backend = win
    backend.calls.clear()
    backend.state["brightness"] = 44
    backend.changed()
    pump()
    assert not [c for c in backend.calls if c[0].startswith("Set")]
    assert int(window._brightness.get_value()) == 44
