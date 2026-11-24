"""Synchronous and asynchronous D-Bus client helpers shared by the CLI and the GUI."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import dbus_api  # noqa: E402

CALL_TIMEOUT_MS = 30000


class ClientError(Exception):
    """A D-Bus call failed. `kind` is the short error name, e.g. InvalidArgument."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def _translate(exc: GLib.Error) -> ClientError:
    text = exc.message
    name = Gio.DBusError.get_remote_error(exc) or ""
    if name.startswith(dbus_api.BUS_NAME + ".Error."):
        message = re.sub(r"^GDBus\.Error:[^:]+: ", "", text)
        return ClientError(name.rsplit(".", 1)[1], message)
    if exc.matches(Gio.dbus_error_quark(), Gio.DBusError.SERVICE_UNKNOWN) or exc.matches(
        Gio.dbus_error_quark(), Gio.DBusError.NAME_HAS_NO_OWNER
    ):
        return ClientError(
            "DaemonNotRunning", "avell-rgbd is not running (is the service started?)"
        )
    return ClientError("Failed", text)


def _opts(options: dict[str, Any] | None) -> GLib.Variant:
    out: dict[str, GLib.Variant] = {}
    for key, value in (options or {}).items():
        if isinstance(value, bool):
            out[key] = GLib.Variant("b", value)
        elif isinstance(value, int):
            out[key] = GLib.Variant("u", value)
        elif isinstance(value, (list, tuple)):
            out[key] = GLib.Variant("as", list(value))
        else:
            out[key] = GLib.Variant("s", str(value))
    return GLib.Variant("a{sv}", out)


class Client:
    def __init__(self, bus: str = "system", connection: Gio.DBusConnection | None = None) -> None:
        self._bus = bus
        self._conn = connection
        self._proxy: Gio.DBusProxy | None = None

    @property
    def connection(self) -> Gio.DBusConnection:
        if self._conn is None:
            kind = Gio.BusType.SYSTEM if self._bus == "system" else Gio.BusType.SESSION
            try:
                self._conn = Gio.bus_get_sync(kind, None)
            except GLib.Error as exc:
                raise ClientError(
                    "NoBus", f"cannot connect to the {self._bus} bus: {exc.message}"
                ) from exc
        return self._conn

    @property
    def proxy(self) -> Gio.DBusProxy:
        if self._proxy is None:
            try:
                self._proxy = Gio.DBusProxy.new_sync(
                    self.connection,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    dbus_api.BUS_NAME,
                    dbus_api.OBJECT_PATH,
                    dbus_api.INTERFACE,
                    None,
                )
            except GLib.Error as exc:
                raise _translate(exc) from exc
        return self._proxy

    def call(self, method: str, params: GLib.Variant | None = None) -> Any:
        try:
            result = self.proxy.call_sync(
                method, params, Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None
            )
        except GLib.Error as exc:
            raise _translate(exc) from exc
        return result.unpack() if result is not None else None

    def call_async(
        self,
        method: str,
        params: GLib.Variant | None,
        callback: Callable[[Any, ClientError | None], None],
    ) -> None:
        def done(proxy: Gio.DBusProxy, res: Gio.AsyncResult) -> None:
            try:
                result = proxy.call_finish(res)
            except GLib.Error as exc:
                callback(None, _translate(exc))
                return
            callback(result.unpack() if result is not None else None, None)

        try:
            self.proxy.call(method, params, Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None, done)
        except ClientError as exc:
            callback(None, exc)

    def watch(self, on_presence: Callable[[bool], None], on_changed: Callable[[], None]) -> None:
        """Report daemon appearing/vanishing and its StateChanged signal (needs a main loop)."""
        Gio.bus_watch_name_on_connection(
            self.connection,
            dbus_api.BUS_NAME,
            Gio.BusNameWatcherFlags.NONE,
            lambda _c, _n, _o: on_presence(True),
            lambda _c, _n: on_presence(False),
        )
        self.connection.signal_subscribe(
            dbus_api.BUS_NAME,
            dbus_api.INTERFACE,
            "StateChanged",
            dbus_api.OBJECT_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            lambda *_args: on_changed(),
        )

    # --- typed wrappers (parameters built here so callers stay simple) --------
    @staticmethod
    def p_zones(colors: list[str]) -> GLib.Variant:
        return GLib.Variant("(as)", (colors,))

    @staticmethod
    def p_zone(zone: int, color: str) -> GLib.Variant:
        return GLib.Variant("(us)", (zone, color))

    @staticmethod
    def p_uint(value: int) -> GLib.Variant:
        return GLib.Variant("(u)", (value,))

    @staticmethod
    def p_bool(value: bool) -> GLib.Variant:
        return GLib.Variant("(b)", (value,))

    @staticmethod
    def p_str(value: str) -> GLib.Variant:
        return GLib.Variant("(s)", (value,))

    @staticmethod
    def p_named(name: str, options: dict[str, Any] | None) -> GLib.Variant:
        return GLib.Variant.new_tuple(GLib.Variant("s", name), _opts(options))

    def set_zones(self, colors: list[str]) -> None:
        self.call("SetZones", self.p_zones(colors))

    def set_zone(self, zone: int, color: str) -> None:
        self.call("SetZone", self.p_zone(zone, color))

    def set_brightness(self, value: int) -> None:
        self.call("SetBrightness", self.p_uint(value))

    def set_power(self, on: bool) -> None:
        self.call("SetPower", self.p_bool(on))

    def set_effect(self, name: str, options: dict[str, Any] | None = None) -> None:
        self.call("SetEffect", self.p_named(name, options))

    def identify_zone(self, zone: int) -> None:
        self.call("IdentifyZone", self.p_uint(zone))

    def start_software_effect(self, name: str, options: dict[str, Any] | None = None) -> None:
        self.call("StartSoftwareEffect", self.p_named(name, options))

    def stop_software_effect(self) -> None:
        self.call("StopSoftwareEffect")

    def list_effects(self) -> tuple[list[str], list[str]]:
        firmware, software = self.call("ListEffects")
        return list(firmware), list(software)

    def save_profile(self, name: str) -> None:
        self.call("SaveProfile", self.p_str(name))

    def load_profile(self, name: str) -> None:
        self.call("LoadProfile", self.p_str(name))

    def delete_profile(self, name: str) -> None:
        self.call("DeleteProfile", self.p_str(name))

    def list_profiles(self) -> list[str]:
        return list(self.call("ListProfiles")[0])

    def get_state(self) -> dict[str, Any]:
        return dict(self.call("GetState")[0])
