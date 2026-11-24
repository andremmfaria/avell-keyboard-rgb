"""Exports the Controller on D-Bus with Gio (GDBus), gates changes with polkit."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import dbus_api  # noqa: E402
from .controller import Controller  # noqa: E402
from .hidraw import DeviceError  # noqa: E402
from .state import InvalidArgument, ProfileNotFound  # noqa: E402

log = logging.getLogger(__name__)

LOGIND_NAME = "org.freedesktop.login1"
LOGIND_PATH = "/org/freedesktop/login1"
LOGIND_IFACE = "org.freedesktop.login1.Manager"
RESUME_DELAY_SECONDS = 1.0


class GLibScheduler:
    """Scheduler backed by GLib timeouts; cancelling a source that already fired is safe."""

    def __init__(self) -> None:
        self._live: set[int] = set()

    def call_later(self, seconds: float, fn: Callable[[], None]) -> object:
        ids: list[int] = []

        def fire() -> bool:
            self._live.discard(ids[0])
            fn()
            return False

        ids.append(GLib.timeout_add(max(1, int(seconds * 1000)), fire))
        self._live.add(ids[0])
        return ids[0]

    def cancel(self, handle: object) -> None:
        if isinstance(handle, int) and handle in self._live:
            self._live.discard(handle)
            GLib.source_remove(handle)


class AllowAllAuthorizer:
    """Used with --no-polkit for development on a private bus."""

    def check(self, connection: Any, sender: str, callback: Callable[[bool], None]) -> None:
        callback(True)


class PolkitAuthorizer:
    def check(self, connection: Any, sender: str, callback: Callable[[bool], None]) -> None:
        subject = ("system-bus-name", {"name": GLib.Variant("s", sender)})
        params = GLib.Variant("((sa{sv})sa{ss}us)", (subject, dbus_api.POLKIT_ACTION, {}, 0, ""))

        def done(conn: Any, result: Any) -> None:
            try:
                reply = conn.call_finish(result).unpack()
                callback(bool(reply[0]))
            except GLib.Error as exc:
                log.error("polkit check failed: %s", exc.message)
                if "trusted callers" in exc.message:
                    log.error(
                        "polkit only lets the action owner check other users' callers: "
                        "the action in io.github.andremmfaria.AvellRgb.policy needs the "
                        "org.freedesktop.policykit.owner annotation naming the daemon user"
                    )
                callback(False)

        connection.call(
            "org.freedesktop.PolicyKit1",
            "/org/freedesktop/PolicyKit1/Authority",
            "org.freedesktop.PolicyKit1.Authority",
            "CheckAuthorization",
            params,
            None,
            Gio.DBusCallFlags.NONE,
            10000,
            None,
            done,
        )


def to_variant(value: Any) -> GLib.Variant:
    if isinstance(value, bool):
        return GLib.Variant("b", value)
    if isinstance(value, int):
        return GLib.Variant("u" if value >= 0 else "i", value)
    if isinstance(value, float):
        return GLib.Variant("d", value)
    if isinstance(value, str):
        return GLib.Variant("s", value)
    if isinstance(value, (list, tuple)):
        return GLib.Variant("as", [str(v) for v in value])
    if isinstance(value, dict):
        return GLib.Variant("a{sv}", {k: to_variant(v) for k, v in value.items() if v is not None})
    raise TypeError(f"cannot encode {type(value)!r}")


class Service:
    def __init__(
        self,
        controller: Controller,
        authorizer: Any,
        scheduler: GLibScheduler,
    ) -> None:
        self.controller = controller
        self._authorizer = authorizer
        self._scheduler = scheduler
        self._connection: Any = None
        self._registration = 0
        self._node = Gio.DBusNodeInfo.new_for_xml(dbus_api.INTERFACE_XML)
        controller.listeners.append(self._emit_changed)
        self._methods: dict[str, Callable[..., GLib.Variant | None]] = {
            "SetZones": lambda colors: controller.set_zones(list(colors)),
            "SetZone": controller.set_zone,
            "SetBrightness": controller.set_brightness,
            "SetPower": controller.set_power,
            "SetEffect": controller.set_effect,
            "IdentifyZone": controller.identify_zone,
            "StartSoftwareEffect": controller.start_software_effect,
            "StopSoftwareEffect": controller.stop_software_effect,
            "SaveProfile": controller.save_profile,
            "LoadProfile": controller.load_profile,
            "DeleteProfile": controller.delete_profile,
            "ListEffects": lambda: GLib.Variant(
                "(asas)", (controller.firmware_effects(), controller.software_effects())
            ),
            "ListProfiles": lambda: GLib.Variant("(as)", (controller.list_profiles(),)),
            "GetState": lambda: GLib.Variant.new_tuple(to_variant(controller.snapshot())),
        }

    # --- registration ------------------------------------------------------
    def register(self, connection: Any) -> None:
        self._connection = connection
        self._registration = connection.register_object(
            dbus_api.OBJECT_PATH,
            self._node.interfaces[0],
            self._on_method_call,
            self._on_get_property,
            None,
        )

    def unregister(self) -> None:
        if self._connection is not None and self._registration:
            self._connection.unregister_object(self._registration)
            self._registration = 0

    def watch_logind(self, system_bus: Any) -> None:
        system_bus.signal_subscribe(
            LOGIND_NAME,
            LOGIND_IFACE,
            "PrepareForSleep",
            LOGIND_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_prepare_for_sleep,
        )

    def _on_prepare_for_sleep(
        self, _c: Any, _s: Any, _p: Any, _i: Any, _n: Any, params: Any
    ) -> None:
        (going_to_sleep,) = params.unpack()
        if going_to_sleep:
            return
        log.info("resumed from suspend, re-applying state")
        self._scheduler.call_later(RESUME_DELAY_SECONDS, self._reapply_after_resume)

    def _reapply_after_resume(self) -> None:
        try:
            self.controller.reapply()
        except DeviceError as exc:
            log.warning("re-apply after resume failed, will retry: %s", exc)

    # --- properties --------------------------------------------------------
    def _properties(self) -> dict[str, GLib.Variant]:
        snap = self.controller.snapshot()
        return {
            "Version": GLib.Variant("s", snap["version"]),
            "DeviceConnected": GLib.Variant("b", snap["device_connected"]),
            "Power": GLib.Variant("b", snap["power"]),
            "Brightness": GLib.Variant("u", snap["brightness"]),
            "Zones": GLib.Variant("as", snap["zones"]),
            "Mode": GLib.Variant("s", snap["mode"]),
            "SoftwareEffect": GLib.Variant("s", snap["software_effect"]),
        }

    def _on_get_property(
        self, _c: Any, _s: Any, _p: Any, _i: Any, name: str
    ) -> GLib.Variant | None:
        return self._properties().get(name)

    def _emit_changed(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.emit_signal(
                None,
                dbus_api.OBJECT_PATH,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (dbus_api.INTERFACE, self._properties(), [])),
            )
            self._connection.emit_signal(
                None, dbus_api.OBJECT_PATH, dbus_api.INTERFACE, "StateChanged", None
            )
        except GLib.Error as exc:
            log.warning("cannot emit signal: %s", exc.message)

    # --- method calls ------------------------------------------------------
    def _on_method_call(
        self,
        connection: Any,
        sender: str,
        _path: str,
        _iface: str,
        method: str,
        parameters: Any,
        invocation: Any,
    ) -> None:
        handler = self._methods.get(method)
        if handler is None:
            invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
            return
        args = parameters.unpack()

        def run(allowed: bool) -> None:
            if not allowed:
                invocation.return_dbus_error(dbus_api.ERR_NOT_AUTHORIZED, "not authorized")
                return
            try:
                result = handler(*args)
            except InvalidArgument as exc:
                invocation.return_dbus_error(dbus_api.ERR_INVALID, str(exc))
            except ProfileNotFound as exc:
                invocation.return_dbus_error(dbus_api.ERR_NOT_FOUND, f"no such profile: {exc}")
            except DeviceError as exc:
                invocation.return_dbus_error(dbus_api.ERR_DEVICE, str(exc))
            except Exception as exc:  # noqa: BLE001 - never let a handler bug kill the daemon
                log.exception("method %s failed", method)
                invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(exc))
            else:
                invocation.return_value(result)

        if method in dbus_api.READ_ONLY_METHODS:
            run(True)
        else:
            self._authorizer.check(connection, sender, run)
