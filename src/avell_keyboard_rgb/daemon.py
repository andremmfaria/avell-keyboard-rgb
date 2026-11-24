"""avell-rgbd: system D-Bus daemon that owns the keyboard."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

try:
    gi.require_version("GLibUnix", "2.0")
    from gi.repository import GLibUnix
except (ValueError, ImportError):
    GLibUnix = None

from . import __version__, dbus_api  # noqa: E402
from .controller import Controller  # noqa: E402
from .dbus_service import AllowAllAuthorizer, GLibScheduler, PolkitAuthorizer, Service  # noqa: E402
from .state import DEFAULT_STATE_DIR, StateStore  # noqa: E402

log = logging.getLogger("avell-rgbd")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avell-rgbd",
        description="D-Bus daemon for the 4 zone ITE 8291 (048d:ce00 rev 0.02) keyboard backlight.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--bus",
        choices=("system", "session"),
        default="system",
        help="bus to own the name on (session is for development and tests)",
    )
    parser.add_argument(
        "--state-dir", type=Path, default=DEFAULT_STATE_DIR, help="state and profile directory"
    )
    parser.add_argument(
        "--no-polkit",
        action="store_true",
        help="skip authorisation checks (development on a session bus only)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.no_polkit and args.bus != "session":
        log.error("--no-polkit is only allowed with --bus session")
        return 2

    scheduler = GLibScheduler()
    controller = Controller(StateStore(args.state_dir), scheduler)
    service = Service(
        controller, AllowAllAuthorizer() if args.no_polkit else PolkitAuthorizer(), scheduler
    )
    loop = GLib.MainLoop()
    exit_code = [0]

    def on_bus(connection: Gio.DBusConnection, _name: str) -> None:
        service.register(connection)
        if args.bus == "system":
            service.watch_logind(connection)

    def on_acquired(_connection: Gio.DBusConnection, _name: str) -> None:
        log.info("owning %s on the %s bus", dbus_api.BUS_NAME, args.bus)
        controller.startup()

    def on_lost(_connection: Gio.DBusConnection | None, _name: str) -> None:
        log.error("lost or could not acquire %s", dbus_api.BUS_NAME)
        exit_code[0] = 1
        loop.quit()

    owner = Gio.bus_own_name(
        Gio.BusType.SYSTEM if args.bus == "system" else Gio.BusType.SESSION,
        dbus_api.BUS_NAME,
        Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
        on_bus,
        on_acquired,
        on_lost,
    )

    def stop() -> bool:
        loop.quit()
        return False

    for signum in (signal.SIGTERM, signal.SIGINT):
        if GLibUnix is not None:
            GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signum, stop)
        else:  # GLib older than 2.80
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, stop)
    try:
        loop.run()
    finally:
        controller.shutdown()
        service.unregister()
        Gio.bus_unown_name(owner)
    return exit_code[0]


if __name__ == "__main__":
    sys.exit(main())
