"""Test helper: runs the real Service on the session bus with a fake keyboard.

Every frame the fake keyboard receives is appended to FRAMES_FILE as a hex line.
usage: python -m tests.dbus_server_helper <state_dir> <frames_file> [--deny]
"""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from avell_keyboard_rgb import dbus_api
from avell_keyboard_rgb.controller import Controller
from avell_keyboard_rgb.dbus_service import AllowAllAuthorizer, GLibScheduler, Service
from avell_keyboard_rgb.state import StateStore


class DenyAuthorizer:
    def check(self, connection, sender, callback):  # type: ignore[no-untyped-def]
        callback(False)


class FileTransport:
    def __init__(self, path: Path, frames_file: Path) -> None:
        self.path = path
        self._file = frames_file

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def send(self, frames) -> None:  # type: ignore[no-untyped-def]
        with open(self._file, "a") as handle:
            for frame in frames:
                handle.write(frame.hex() + "\n")


def main() -> None:
    state_dir, frames_file = Path(sys.argv[1]), Path(sys.argv[2])
    scheduler = GLibScheduler()
    controller = Controller(
        StateStore(state_dir),
        scheduler,
        finder=lambda: Path("/dev/hidraw-fake"),
        transport_factory=lambda p: FileTransport(p, frames_file),
    )
    authorizer = DenyAuthorizer() if "--deny" in sys.argv else AllowAllAuthorizer()
    service = Service(controller, authorizer, scheduler)
    loop = GLib.MainLoop()

    def on_bus(connection, name):  # type: ignore[no-untyped-def]
        service.register(connection)

    def on_acquired(connection, name):  # type: ignore[no-untyped-def]
        controller.startup()
        print("ready", flush=True)

    Gio.bus_own_name(
        Gio.BusType.SESSION,
        dbus_api.BUS_NAME,
        Gio.BusNameOwnerFlags.NONE,
        on_bus,
        on_acquired,
        lambda c, n: loop.quit(),
    )
    loop.run()


if __name__ == "__main__":
    main()
