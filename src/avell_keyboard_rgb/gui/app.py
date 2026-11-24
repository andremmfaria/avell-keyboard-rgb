"""avell-rgb-gui entry point."""

from __future__ import annotations

import argparse
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from .. import __version__  # noqa: E402
from ..dbus_client import Client  # noqa: E402
from .window import MainWindow  # noqa: E402

APP_ID = "io.github.andremmfaria.AvellRgbGui"


class App(Adw.Application):
    def __init__(self, client: Client) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self._client = client

    def do_activate(self) -> None:
        window = self.props.active_window or MainWindow(self, self._client)
        window.present()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="avell-rgb-gui", description="GTK4 front end for avell-rgbd."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--bus", choices=("system", "session"), default="system")
    args, rest = parser.parse_known_args(argv)
    return App(Client(args.bus)).run([sys.argv[0], *rest])


if __name__ == "__main__":
    sys.exit(main())
