"""Software effects engine: effects compute 4 zone colours; the engine paces writes."""

from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import protocol
from .protocol import RGB
from .state import InvalidArgument, check_range, norm_color

DEFAULT_FPS = 10
MIN_FPS = 1
MAX_FPS = 20
SENSOR_CACHE_SECONDS = 1.0

OFF: RGB = (0, 0, 0)


def lerp(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def ramp(stops: list[RGB], t: float, *, wrap: bool = False) -> RGB:
    """Colour at position t (0..1) along evenly spaced stops; wrap blends last to first."""
    if len(stops) == 1:
        return stops[0]
    points = stops + [stops[0]] if wrap else stops
    t = t % 1.0 if wrap else max(0.0, min(1.0, t))
    scaled = t * (len(points) - 1)
    index = min(int(scaled), len(points) - 2)
    return lerp(points[index], points[index + 1], scaled - index)


class Sensors:
    """Reads CPU temperature and battery state from sysfs, with a short cache."""

    def __init__(
        self,
        hwmon_root: Path = Path("/sys/class/hwmon"),
        power_root: Path = Path("/sys/class/power_supply"),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._hwmon = hwmon_root
        self._power = power_root
        self._clock = clock
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cached(self, key: str, read: Callable[[], Any]) -> Any:
        now = self._clock()
        hit = self._cache.get(key)
        if hit and now - hit[0] < SENSOR_CACHE_SECONDS:
            return hit[1]
        value = read()
        self._cache[key] = (now, value)
        return value

    def cpu_temp(self) -> float | None:
        return self._cached("cpu_temp", self._read_cpu_temp)

    def _read_cpu_temp(self) -> float | None:
        wanted = ("coretemp", "k10temp", "zenpower", "cpu_thermal")
        try:
            chips = sorted(self._hwmon.glob("hwmon*"))
        except OSError:
            return None
        for chip in chips:
            try:
                name = (chip / "name").read_text().strip()
            except OSError:
                continue
            if name not in wanted:
                continue
            temps: list[float] = []
            for node in chip.glob("temp*_input"):
                try:
                    temps.append(int(node.read_text().strip()) / 1000.0)
                except (OSError, ValueError):
                    continue
            if temps:
                return max(temps)
        return None

    def battery(self) -> tuple[int | None, bool]:
        """Return (percent or None, charging)."""
        return self._cached("battery", self._read_battery)

    def _read_battery(self) -> tuple[int | None, bool]:
        try:
            supplies = sorted(self._power.glob("BAT*"))
        except OSError:
            return (None, False)
        for supply in supplies:
            try:
                percent = int((supply / "capacity").read_text().strip())
                status = (supply / "status").read_text().strip()
            except (OSError, ValueError):
                continue
            return (max(0, min(100, percent)), status == "Charging")
        return (None, False)


class SoftwareEffect(ABC):
    name = ""

    @abstractmethod
    def render(self, now: float, sensors: Sensors) -> list[RGB]:
        """Return exactly 4 zone colours for time `now` (seconds, monotonic)."""


class CpuTempEffect(SoftwareEffect):
    """Whole keyboard goes green to yellow to red between min_temp and max_temp."""

    name = "cpu-temp"
    STOPS: list[RGB] = [(0, 255, 0), (255, 200, 0), (255, 0, 0)]

    def __init__(self, min_temp: int, max_temp: int) -> None:
        self.min_temp = min_temp
        self.max_temp = max_temp

    def render(self, now: float, sensors: Sensors) -> list[RGB]:
        temp = sensors.cpu_temp()
        if temp is None:
            return [(0, 0, 255)] * protocol.ZONE_COUNT
        span = max(1, self.max_temp - self.min_temp)
        colour = ramp(self.STOPS, (temp - self.min_temp) / span)
        return [colour] * protocol.ZONE_COUNT


class BatteryEffect(SoftwareEffect):
    """Zones act as a 4 step bar. Charging makes the top lit zone breathe."""

    name = "battery"

    def render(self, now: float, sensors: Sensors) -> list[RGB]:
        percent, charging = sensors.battery()
        if percent is None:
            return [(0, 0, 255)] * protocol.ZONE_COUNT
        if percent < 20:
            colour: RGB = (255, 0, 0)
        elif percent < 50:
            colour = (255, 160, 0)
        else:
            colour = (0, 255, 0)
        lit = max(1, math.ceil(percent / 25))
        zones = [colour if i < lit else OFF for i in range(protocol.ZONE_COUNT)]
        if charging:
            phase = (math.sin(now * math.pi) + 1) / 2
            zones[lit - 1] = lerp(OFF, colour, 0.25 + 0.75 * phase)
        return zones


class FadeEffect(SoftwareEffect):
    """Slow colour cycle; each zone is a quarter of a period behind its neighbour."""

    name = "fade"

    def __init__(self, period: int, colors: list[RGB]) -> None:
        self.period = period
        self.colors = colors

    def render(self, now: float, sensors: Sensors) -> list[RGB]:
        base = now / self.period
        count = protocol.ZONE_COUNT
        return [ramp(self.colors, base + i / count, wrap=True) for i in range(count)]


FADE_DEFAULT_COLORS = ["ff0000", "0000ff", "00ff00"]


def _check_options(name: str, options: dict[str, Any], known: set[str]) -> None:
    extra = set(options) - known - {"fps"}
    if extra:
        raise InvalidArgument(f"unknown option(s) for {name}: {', '.join(sorted(extra))}")


def create_effect(name: str, options: dict[str, Any]) -> tuple[SoftwareEffect, dict[str, Any]]:
    """Validate options and build an effect. Returns (effect, normalised options)."""
    fps = check_range("fps", options.get("fps", DEFAULT_FPS), MIN_FPS, MAX_FPS)
    if name == "cpu-temp":
        _check_options(name, options, {"min_temp", "max_temp"})
        lo = check_range("min_temp", options.get("min_temp", 40), 0, 120)
        hi = check_range("max_temp", options.get("max_temp", 90), 1, 130)
        if hi <= lo:
            raise InvalidArgument("max_temp must be greater than min_temp")
        return CpuTempEffect(lo, hi), {"fps": fps, "min_temp": lo, "max_temp": hi}
    if name == "battery":
        _check_options(name, options, set())
        return BatteryEffect(), {"fps": fps}
    if name == "fade":
        _check_options(name, options, {"period", "colors"})
        period = check_range("period", options.get("period", 30), 2, 3600)
        raw = options.get("colors", FADE_DEFAULT_COLORS)
        if not isinstance(raw, (list, tuple)) or not 1 <= len(raw) <= 16:
            raise InvalidArgument("colors must hold 1 to 16 colours")
        names = [norm_color(c) for c in raw]
        return (
            FadeEffect(period, [protocol.parse_color(c) for c in names]),
            {"fps": fps, "period": period, "colors": names},
        )
    raise InvalidArgument(f"unknown software effect {name!r}")


SOFTWARE_EFFECTS: tuple[str, ...] = ("cpu-temp", "battery", "fade")


class SoftwareEffectEngine:
    """Calls `apply(colors)` at most `fps` times a second, and never with an unchanged frame."""

    def __init__(
        self,
        apply: Callable[[list[RGB]], None],
        *,
        clock: Callable[[], float] = time.monotonic,
        sensors: Sensors | None = None,
    ) -> None:
        self._apply = apply
        self._clock = clock
        self._sensors = sensors or Sensors(clock=clock)
        self._effect: SoftwareEffect | None = None
        self._interval = 1.0 / DEFAULT_FPS
        self._last_tick: float | None = None
        self._last_frame: list[RGB] | None = None
        self.name = ""
        self.options: dict[str, Any] = {}

    @property
    def running(self) -> bool:
        return self._effect is not None

    @property
    def interval(self) -> float:
        return self._interval

    def start(self, name: str, options: dict[str, Any]) -> dict[str, Any]:
        effect, normalised = create_effect(name, options)
        self._effect = effect
        self.name = name
        self.options = normalised
        self._interval = 1.0 / normalised["fps"]
        self._last_tick = None
        self._last_frame = None
        return normalised

    def stop(self) -> None:
        self._effect = None
        self.name = ""
        self.options = {}
        self._last_frame = None

    def invalidate(self) -> None:
        """Forget the last frame so the next tick writes again (after resume or a mode change)."""
        self._last_frame = None

    def tick(self) -> bool:
        """Render and apply one frame if due. Returns True when a frame was written."""
        if self._effect is None:
            return False
        now = self._clock()
        if self._last_tick is not None and now - self._last_tick < self._interval * 0.999:
            return False
        self._last_tick = now
        frame = self._effect.render(now, self._sensors)
        if frame == self._last_frame:
            return False
        self._apply(frame)
        self._last_frame = frame
        return True
