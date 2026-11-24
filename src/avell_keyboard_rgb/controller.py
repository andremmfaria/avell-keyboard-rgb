"""Daemon core without any D-Bus or GLib dependency: state, device access, effects, timers."""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from . import __version__, protocol
from .effects import SOFTWARE_EFFECTS, Sensors, SoftwareEffectEngine, create_effect
from .hidraw import DeviceError, HidrawTransport, find_device
from .protocol import RGB
from .state import (
    InvalidArgument,
    State,
    StateStore,
    check_range,
    norm_color,
    norm_effect,
    norm_zone,
)

log = logging.getLogger(__name__)

RECONNECT_SECONDS = 5.0
PERSIST_DELAY_SECONDS = 1.0
IDENTIFY_STEP_SECONDS = 0.25
IDENTIFY_FLASHES = 3
IDENTIFY_MIN_BRIGHTNESS = 25


class Transport(Protocol):
    path: Path

    def open(self) -> None: ...
    def close(self) -> None: ...
    def send(self, frames: Any) -> None: ...


class Scheduler(Protocol):
    def call_later(self, seconds: float, fn: Callable[[], None]) -> object: ...
    def cancel(self, handle: object) -> None: ...


class Controller:
    def __init__(
        self,
        store: StateStore,
        scheduler: Scheduler,
        *,
        finder: Callable[[], Path | None] = find_device,
        transport_factory: Callable[[Path], Transport] = HidrawTransport,
        clock: Callable[[], float] = time.monotonic,
        sensors: Sensors | None = None,
    ) -> None:
        self.store = store
        self._scheduler = scheduler
        self._finder = finder
        self._factory = transport_factory
        self._transport: Transport | None = None
        self.state = self._sanitize(store.load())
        self.connected = False
        self.last_error = ""
        self.listeners: list[Callable[[], None]] = []
        self._engine = SoftwareEffectEngine(
            self._write_software_frame, clock=clock, sensors=sensors
        )
        self._tick_handle: object | None = None
        self._reconnect_handle: object | None = None
        self._persist_handle: object | None = None
        self._identify_handle: object | None = None
        self._identifying = False

    @staticmethod
    def _sanitize(state: State) -> State:
        """Drop a stored software effect that no longer validates (hand edited file)."""
        if state.software:
            try:
                _, state.software["options"] = create_effect(
                    state.software["name"], state.software["options"]
                )
            except InvalidArgument as exc:
                log.warning("dropping stored software effect: %s", exc)
                state.software = None
        return state

    # --- lifecycle ---------------------------------------------------------
    def startup(self) -> None:
        """Apply stored state. A missing keyboard is not fatal; it is retried."""
        try:
            self.reapply()
        except DeviceError as exc:
            log.warning("keyboard not available at start: %s", exc)

    def shutdown(self) -> None:
        self._cancel_identify()
        self._cancel_tick()
        if self._reconnect_handle is not None:
            self._scheduler.cancel(self._reconnect_handle)
            self._reconnect_handle = None
        self.flush()
        self._close_transport()

    def flush(self) -> None:
        if self._persist_handle is not None:
            self._scheduler.cancel(self._persist_handle)
            self._persist_handle = None
        try:
            self.store.save(self.state)
        except OSError as exc:
            log.error("cannot store state: %s", exc)

    # --- device ------------------------------------------------------------
    def _close_transport(self) -> None:
        if self._transport is not None:
            with contextlib.suppress(OSError):
                self._transport.close()
            self._transport = None

    def _device(self) -> Transport:
        if self._transport is not None:
            return self._transport
        path = self._finder()
        if path is None:
            raise DeviceError("keyboard 048d:ce00 not found")
        transport = self._factory(path)
        transport.open()
        self._transport = transport
        return transport

    def _send(self, frames: list[bytes]) -> None:
        try:
            self._device().send(frames)
        except DeviceError as exc:
            self._close_transport()
            self._set_connected(False, str(exc))
            self._schedule_reconnect()
            raise
        self._set_connected(True, "")

    def _set_connected(self, connected: bool, error: str) -> None:
        changed = connected != self.connected
        self.connected = connected
        self.last_error = error
        if changed:
            log.info("keyboard %s", "connected" if connected else f"unavailable: {error}")
            self._notify()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_handle is None:
            self._reconnect_handle = self._scheduler.call_later(RECONNECT_SECONDS, self._retry)

    def _retry(self) -> None:
        self._reconnect_handle = None
        with contextlib.suppress(DeviceError):
            self.reapply()

    # --- applying state ----------------------------------------------------
    def reapply(self) -> None:
        """Write the whole stored state to the keyboard. Raises DeviceError on failure."""
        self._cancel_tick()
        self._engine.stop()
        state = self.state
        if not state.power:
            self._send([protocol.off_frame()])
            return
        if state.software:
            self._engine.start(state.software["name"], state.software["options"])
            self._engine.tick()
            self._schedule_tick()
            return
        if state.effect:
            e = state.effect
            palette = [protocol.parse_color(c) for c in e["palette"]]
            self._send(
                protocol.effect_frames(
                    e["name"], e["speed"], state.brightness, palette, e["direction"]
                )
            )
            return
        self._send(
            protocol.zones_frames([protocol.parse_color(c) for c in state.zones], state.brightness)
        )

    def _write_software_frame(self, colors: list[RGB]) -> None:
        self._send(protocol.zones_frames(colors, self.state.brightness))

    def _schedule_tick(self) -> None:
        self._cancel_tick()
        if self._engine.running:
            self._tick_handle = self._scheduler.call_later(self._engine.interval, self._on_tick)

    def _cancel_tick(self) -> None:
        if self._tick_handle is not None:
            self._scheduler.cancel(self._tick_handle)
            self._tick_handle = None

    def _on_tick(self) -> None:
        self._tick_handle = None
        if not self._engine.running:
            return
        if self.state.power and not self._identifying:
            try:
                self._engine.tick()
            except DeviceError:
                # The reconnect timer calls reapply(), which restarts ticking.
                return
        self._schedule_tick()

    def _notify(self) -> None:
        for listener in list(self.listeners):
            listener()

    def _persist_later(self) -> None:
        if self._persist_handle is None:
            self._persist_handle = self._scheduler.call_later(PERSIST_DELAY_SECONDS, self.flush)

    def _commit(self) -> None:
        """Store state, tell listeners, apply to the device (raises DeviceError)."""
        self._cancel_identify()
        self._persist_later()
        self._notify()
        self.reapply()

    # --- commands ----------------------------------------------------------
    def set_zones(self, colors: list[str]) -> None:
        if len(colors) != protocol.ZONE_COUNT:
            raise InvalidArgument(f"expected {protocol.ZONE_COUNT} colours")
        self.state.zones = [norm_color(c) for c in colors]
        self.state.effect = None
        self.state.software = None
        self.state.power = True
        self._commit()

    def set_zone(self, zone: int, color: str) -> None:
        index = norm_zone(zone)
        colour = norm_color(color)
        self.state.zones[index - 1] = colour
        self.state.effect = None
        self.state.software = None
        self.state.power = True
        self._commit()

    def set_brightness(self, value: int) -> None:
        self.state.brightness = check_range(
            "brightness", value, protocol.BRIGHTNESS_MIN, protocol.BRIGHTNESS_MAX
        )
        self._commit()

    def set_power(self, on: bool) -> None:
        if not isinstance(on, bool):
            raise InvalidArgument("power must be a boolean")
        self.state.power = on
        self._commit()

    def set_effect(self, name: str, options: dict[str, Any]) -> None:
        if name == "static":
            if options:
                raise InvalidArgument("static takes no options")
            self.state.effect = None
        else:
            self.state.effect = norm_effect(name, options)
        self.state.software = None
        self.state.power = True
        self._commit()

    def start_software_effect(self, name: str, options: dict[str, Any]) -> None:
        # Validate before touching state: create_effect raises InvalidArgument on bad input.
        _, normalised = create_effect(name, options)
        self.state.software = {"name": name, "options": normalised}
        self.state.effect = None
        self.state.power = True
        self._commit()

    def stop_software_effect(self) -> None:
        self.state.software = None
        self._commit()

    def identify_zone(self, zone: int) -> None:
        index = norm_zone(zone)
        self._cancel_identify()
        self._cancel_tick()
        self._engine.stop()
        self._identifying = True
        brightness = max(self.state.brightness, IDENTIFY_MIN_BRIGHTNESS)
        on = [(255, 255, 255) if i == index - 1 else (0, 0, 0) for i in range(protocol.ZONE_COUNT)]
        off = [(0, 0, 0)] * protocol.ZONE_COUNT
        steps = [on if i % 2 == 0 else off for i in range(IDENTIFY_FLASHES * 2 - 1)]

        def run(position: int) -> None:
            self._identify_handle = None
            if position >= len(steps):
                self._identifying = False
                with contextlib.suppress(DeviceError):
                    self.reapply()
                return
            try:
                self._send(protocol.zones_frames(steps[position], brightness))
            except DeviceError:
                self._identifying = False
                return
            self._identify_handle = self._scheduler.call_later(
                IDENTIFY_STEP_SECONDS, lambda: run(position + 1)
            )

        run(0)

    def _cancel_identify(self) -> None:
        if self._identify_handle is not None:
            self._scheduler.cancel(self._identify_handle)
            self._identify_handle = None
        self._identifying = False

    def save_profile(self, name: str) -> None:
        self.store.save_profile(name, self.state)

    def load_profile(self, name: str) -> None:
        self.state = self._sanitize(self.store.load_profile(name))
        self._commit()

    def delete_profile(self, name: str) -> None:
        self.store.delete_profile(name)

    def list_profiles(self) -> list[str]:
        return self.store.list_profiles()

    def save_to_firmware(self) -> None:
        """Experimental. The only place the SAVE byte and the persist frame are ever sent."""
        state = self.state
        if not state.power or state.software:
            raise InvalidArgument("power on and stop software effects before saving to firmware")
        if state.effect:
            e = state.effect
            frames = protocol.effect_frames(
                e["name"],
                e["speed"],
                state.brightness,
                [protocol.parse_color(c) for c in e["palette"]],
                e["direction"],
                save=True,
            )
        else:
            frames = protocol.zones_frames(
                [protocol.parse_color(c) for c in state.zones], state.brightness, save=True
            )
        frames.append(protocol.persist_frame())
        self._send(frames)

    # --- queries -----------------------------------------------------------
    def firmware_effects(self) -> list[str]:
        return list(protocol.FIRMWARE_EFFECTS)

    def software_effects(self) -> list[str]:
        return list(SOFTWARE_EFFECTS)

    def snapshot(self) -> dict[str, Any]:
        s: State = self.state
        return {
            "version": __version__,
            "device_connected": self.connected,
            "device_path": str(self._transport.path) if self._transport else "",
            "power": s.power,
            "brightness": s.brightness,
            "zones": list(s.zones),
            "mode": s.mode,
            "effect": s.effect,
            "software_effect": s.software["name"] if s.software else "",
            "software_options": s.software["options"] if s.software else {},
            "last_error": self.last_error,
        }
