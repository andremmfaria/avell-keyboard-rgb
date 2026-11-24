"""Main window. Uses only widgets available in libadwaita 1.5 (Ubuntu 24.04) and GTK 4.14."""

from __future__ import annotations

from typing import Any, Protocol

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from .. import protocol  # noqa: E402
from ..dbus_client import Client, ClientError  # noqa: E402

EFFECT_LABELS = ["Static colours", *[n.capitalize() for n in protocol.FIRMWARE_EFFECTS]]
EFFECT_NAMES = ["static", *protocol.FIRMWARE_EFFECTS]
SOFTWARE_NAMES = ["cpu-temp", "battery", "fade"]
SOFTWARE_LABELS = ["CPU temperature", "Battery level", "Slow fade"]
DEBOUNCE_MS = 150

CSS = b"""
.kbd-outline { border: 3px solid alpha(currentColor, 0.5); border-radius: 18px; padding: 10px; }
.kbd-zone { min-height: 120px; border-radius: 10px; border: 3px solid transparent; }
.kbd-zone:checked { border-color: @accent_bg_color; }
"""


class Backend(Protocol):
    """What the window needs from the D-Bus client (a fake in tests)."""

    def call_async(self, method: str, params: Any, callback: Any) -> None: ...
    def watch(self, on_presence: Any, on_changed: Any) -> None: ...


def _load_css(provider: Gtk.CssProvider, data: bytes) -> None:
    # load_from_string needs GTK 4.12; Ubuntu 24.04 ships 4.14 but keep the older call as fallback.
    if hasattr(provider, "load_from_string"):
        provider.load_from_string(data.decode())
    else:
        provider.load_from_data(data)


def rgba_to_hex(rgba: Gdk.RGBA) -> str:
    return "{:02x}{:02x}{:02x}".format(
        *(max(0, min(255, round(c * 255))) for c in (rgba.red, rgba.green, rgba.blue))
    )


def hex_to_rgba(text: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse("#" + text)
    return rgba


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, client: Backend) -> None:
        super().__init__(
            application=app, title="Avell Keyboard RGB", default_width=560, default_height=820
        )
        self._client = client
        self._updating = False
        self._zone = 1
        self._zones = ["ffffff"] * protocol.ZONE_COUNT
        self._debounce: dict[str, int] = {}
        self._profile_rows: list[Gtk.Widget] = []
        self._install_css()
        self._build()
        client.watch(self._on_presence, self.refresh)
        self.refresh()

    # --- construction ------------------------------------------------------
    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        _load_css(provider, CSS)
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        self._zone_css = Gtk.CssProvider()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display, self._zone_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _build(self) -> None:
        self._toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        self._banner = Adw.Banner(title="The avell-rgbd daemon is not running", revealed=False)
        view.add_top_bar(self._banner)

        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18, margin_top=18, margin_bottom=18
        )
        clamp = Adw.Clamp(maximum_size=520, child=page)
        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, child=clamp, vexpand=True
        )
        view.set_content(scroller)
        self._toasts.set_child(view)
        self.set_content(self._toasts)

        page.append(self._build_keyboard())
        page.append(self._build_zone_group())
        page.append(self._build_light_group())
        page.append(self._build_effect_group())
        page.append(self._build_software_group())
        self._profiles_group = Adw.PreferencesGroup(title="Profiles")
        page.append(self._profiles_group)
        self._build_profile_entry()

    def _build_keyboard(self) -> Gtk.Widget:
        row = Gtk.Box(spacing=8, homogeneous=True)
        row.add_css_class("kbd-outline")
        row.set_tooltip_text("Click a band to select that zone")
        self._zone_buttons: list[Gtk.ToggleButton] = []
        first: Gtk.ToggleButton | None = None
        for i in range(protocol.ZONE_COUNT):
            button = Gtk.ToggleButton(hexpand=True)
            button.add_css_class("kbd-zone")
            button.add_css_class(f"zone-{i + 1}")
            button.update_property([Gtk.AccessibleProperty.LABEL], [f"Zone {i + 1}"])
            if first is None:
                first = button
            else:
                button.set_group(first)
            button.connect("toggled", self._on_zone_toggled, i + 1)
            self._zone_buttons.append(button)
            row.append(button)
        self._zone_buttons[0].set_active(True)
        return row

    def _build_zone_group(self) -> Gtk.Widget:
        self._zone_group = Adw.PreferencesGroup(title="Zone 1")
        self._color_button = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(), valign=Gtk.Align.CENTER
        )
        self._color_button.connect("notify::rgba", self._on_color_set)
        color_row = Adw.ActionRow(title="Colour", subtitle="Applies to the selected band")
        color_row.add_suffix(self._color_button)
        self._zone_group.add(color_row)
        flash = Gtk.Button(label="Flash", valign=Gtk.Align.CENTER)
        flash.connect("clicked", self._on_identify)
        identify_row = Adw.ActionRow(
            title="Flash this zone", subtitle="Blinks the zone to show which one it is"
        )
        identify_row.add_suffix(flash)
        self._zone_group.add(identify_row)
        return self._zone_group

    def _build_light_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(title="Backlight")
        self._power_row = Adw.SwitchRow(title="Backlight on")
        self._power_row.connect("notify::active", self._on_power)
        group.add(self._power_row)
        self._brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, protocol.BRIGHTNESS_MIN, protocol.BRIGHTNESS_MAX, 1
        )
        self._brightness.set_hexpand(True)
        self._brightness.set_size_request(200, -1)
        self._brightness.connect("value-changed", self._on_brightness)
        row = Adw.ActionRow(title="Brightness")
        row.add_suffix(self._brightness)
        group.add(row)
        return group

    def _build_effect_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Keyboard effect", description="Run by the keyboard itself"
        )
        self._effect_row = Adw.ComboRow(title="Effect", model=Gtk.StringList.new(EFFECT_LABELS))
        self._effect_row.connect("notify::selected", self._on_effect)
        group.add(self._effect_row)
        self._speed_row = Adw.SpinRow.new_with_range(protocol.SPEED_MIN, protocol.SPEED_MAX, 1)
        self._speed_row.set_title("Speed")
        self._speed_row.set_value(5)
        self._speed_row.connect("notify::value", self._on_effect)
        group.add(self._speed_row)
        return group

    def _build_software_group(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup(
            title="Software effect",
            description="Driven by the daemon, updates up to 10 times a second",
        )
        self._software_row = Adw.ComboRow(title="Effect", model=Gtk.StringList.new(SOFTWARE_LABELS))
        group.add(self._software_row)
        start = Gtk.Button(label="Start", valign=Gtk.Align.CENTER)
        start.add_css_class("suggested-action")
        start.connect("clicked", self._on_software_start)
        stop = Gtk.Button(label="Stop", valign=Gtk.Align.CENTER)
        stop.connect("clicked", lambda _b: self._call("StopSoftwareEffect", None))
        row = Adw.ActionRow(title="Run")
        self._software_status = row
        row.add_suffix(stop)
        row.add_suffix(start)
        group.add(row)
        return group

    def _build_profile_entry(self) -> None:
        self._name_row = Adw.EntryRow(title="Save current setup as")
        save = Gtk.Button(icon_name="document-save-symbolic", valign=Gtk.Align.CENTER)
        save.set_tooltip_text("Save profile")
        save.update_property([Gtk.AccessibleProperty.LABEL], ["Save profile"])
        save.connect("clicked", self._on_save_profile)
        self._name_row.add_suffix(save)
        self._name_row.connect("apply", self._on_save_profile)
        self._profiles_group.add(self._name_row)

    # --- daemon traffic ----------------------------------------------------
    def _call(self, method: str, params: Any, then: Any = None) -> None:
        def done(result: Any, error: ClientError | None) -> None:
            if error is not None:
                self._toast(f"{error.kind}: {error.message}")
                if error.kind == "DaemonNotRunning":
                    self._banner.set_revealed(True)
            elif then is not None:
                then(result)

        self._client.call_async(method, params, done)

    def _toast(self, text: str) -> None:
        self._toasts.add_toast(Adw.Toast(title=text, timeout=4))

    def _later(self, key: str, fn: Any) -> None:
        """Run fn after DEBOUNCE_MS of quiet, replacing an earlier call with the same key."""
        old = self._debounce.pop(key, 0)
        if old:
            GLib.source_remove(old)

        def fire() -> bool:
            self._debounce.pop(key, None)
            fn()
            return False

        self._debounce[key] = GLib.timeout_add(DEBOUNCE_MS, fire)

    def _on_presence(self, present: bool) -> None:
        self._banner.set_revealed(not present)
        if present:
            self.refresh()

    def refresh(self) -> None:
        self._call("GetState", None, lambda result: self._apply_state(result[0]))
        self._call("ListProfiles", None, lambda result: self._fill_profiles(result[0]))

    # --- state to widgets --------------------------------------------------
    def _apply_state(self, state: dict[str, Any]) -> None:
        self._updating = True
        try:
            self._banner.set_revealed(False)
            if not state.get("device_connected", True):
                self._banner.set_title(
                    "Keyboard not found: " + (state.get("last_error") or "unplugged?")
                )
                self._banner.set_revealed(True)
            self._zones = list(state.get("zones", self._zones))
            self._power_row.set_active(bool(state.get("power", True)))
            self._brightness.set_value(state.get("brightness", 25))
            effect = state.get("effect") or {}
            name = effect.get("name", "static")
            self._effect_row.set_selected(EFFECT_NAMES.index(name) if name in EFFECT_NAMES else 0)
            if effect:
                self._speed_row.set_value(effect.get("speed", 5))
            running = state.get("software_effect", "")
            self._software_status.set_subtitle(f"Running: {running}" if running else "Stopped")
            if running in SOFTWARE_NAMES:
                self._software_row.set_selected(SOFTWARE_NAMES.index(running))
            self._paint_zones()
        finally:
            self._updating = False

    def _paint_zones(self) -> None:
        css = "".join(f".zone-{i + 1} {{ background: #{c}; }}\n" for i, c in enumerate(self._zones))
        _load_css(self._zone_css, css.encode())
        self._color_button.set_rgba(hex_to_rgba(self._zones[self._zone - 1]))
        self._zone_group.set_title(f"Zone {self._zone}")

    def _fill_profiles(self, names: list[str]) -> None:
        for row in self._profile_rows:
            self._profiles_group.remove(row)
        self._profile_rows = []
        for name in names:
            row = Adw.ActionRow(title=GLib.markup_escape_text(name))
            load = Gtk.Button(label="Load", valign=Gtk.Align.CENTER)
            load.connect("clicked", lambda _b, n=name: self._call("LoadProfile", Client.p_str(n)))
            delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER)
            delete.add_css_class("destructive-action")
            delete.update_property([Gtk.AccessibleProperty.LABEL], [f"Delete profile {name}"])
            delete.connect(
                "clicked",
                lambda _b, n=name: self._call(
                    "DeleteProfile", Client.p_str(n), lambda _r: self.refresh()
                ),
            )
            row.add_suffix(load)
            row.add_suffix(delete)
            self._profiles_group.add(row)
            self._profile_rows.append(row)

    # --- widget handlers ---------------------------------------------------
    def _on_zone_toggled(self, button: Gtk.ToggleButton, zone: int) -> None:
        if button.get_active():
            self._zone = zone
            self._updating = True
            try:
                self._paint_zones()
            finally:
                self._updating = False

    def _on_color_set(self, button: Gtk.ColorDialogButton, _pspec: Any) -> None:
        if self._updating:
            return
        color = rgba_to_hex(button.get_rgba())
        zone = self._zone
        self._zones[zone - 1] = color
        self._updating = True
        try:
            self._paint_zones()
        finally:
            self._updating = False
        self._later(f"zone{zone}", lambda: self._call("SetZone", Client.p_zone(zone, color)))

    def _on_identify(self, _button: Gtk.Button) -> None:
        self._call("IdentifyZone", Client.p_uint(self._zone))

    def _on_power(self, row: Adw.SwitchRow, _pspec: Any) -> None:
        if not self._updating:
            self._call("SetPower", Client.p_bool(row.get_active()))

    def _on_brightness(self, scale: Gtk.Scale) -> None:
        if not self._updating:
            value = int(scale.get_value())
            self._later("brightness", lambda: self._call("SetBrightness", Client.p_uint(value)))

    def _on_effect(self, *_args: Any) -> None:
        if self._updating:
            return
        name = EFFECT_NAMES[self._effect_row.get_selected()]
        options = {} if name == "static" else {"speed": int(self._speed_row.get_value())}
        self._later("effect", lambda: self._call("SetEffect", Client.p_named(name, options)))

    def _on_software_start(self, _button: Gtk.Button) -> None:
        name = SOFTWARE_NAMES[self._software_row.get_selected()]
        self._call("StartSoftwareEffect", Client.p_named(name, {}))

    def _on_save_profile(self, *_args: Any) -> None:
        name = self._name_row.get_text().strip()
        if not name:
            return
        self._call(
            "SaveProfile",
            Client.p_str(name),
            lambda _r: self._profile_saved(name),
        )

    def _profile_saved(self, name: str) -> None:
        self._name_row.set_text("")
        self._toast(f"Saved profile {name}")
        self.refresh()
