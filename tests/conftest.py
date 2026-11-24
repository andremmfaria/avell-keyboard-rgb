"""Shared fakes: manual scheduler and clock, recording transport, fake sysfs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from avell_keyboard_rgb.controller import Controller
from avell_keyboard_rgb.effects import Sensors
from avell_keyboard_rgb.hidraw import DeviceError
from avell_keyboard_rgb.state import StateStore


class FakeScheduler:
    """Manual timers. `advance(dt)` moves time and runs everything that became due."""

    def __init__(self) -> None:
        self.now = 1000.0
        self._timers: list[tuple[float, int, Callable[[], None]]] = []
        self._next = 1

    def clock(self) -> float:
        return self.now

    def call_later(self, seconds: float, fn: Callable[[], None]) -> object:
        handle = self._next
        self._next += 1
        self._timers.append((self.now + seconds, handle, fn))
        return handle

    def cancel(self, handle: object) -> None:
        self._timers = [t for t in self._timers if t[1] != handle]

    def advance(self, seconds: float) -> None:
        end = self.now + seconds
        while True:
            due = sorted(t for t in self._timers if t[0] <= end)
            if not due:
                break
            when, handle, fn = due[0]
            self._timers = [t for t in self._timers if t[1] != handle]
            self.now = max(self.now, when)
            fn()
        self.now = end

    @property
    def pending(self) -> int:
        return len(self._timers)


class FakeTransport:
    """Records every 8 byte frame. `fail` makes the next sends raise DeviceError."""

    def __init__(self, path: Path, log: list[bytes], state: dict[str, bool]) -> None:
        self.path = path
        self._log = log
        self._state = state

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def send(self, frames: list[bytes]) -> None:
        if self._state["fail"]:
            raise DeviceError("simulated write failure")
        self._log.extend(frames)


class Rig:
    def __init__(self, tmp_path: Path) -> None:
        self.scheduler = FakeScheduler()
        self.frames: list[bytes] = []
        self.flags = {"fail": False, "present": True}
        self.hwmon = tmp_path / "hwmon"
        self.power = tmp_path / "power"
        self.hwmon.mkdir()
        self.power.mkdir()
        self.store = StateStore(tmp_path / "state")
        self.controller = Controller(
            self.store,
            self.scheduler,
            finder=lambda: Path("/dev/hidraw-fake") if self.flags["present"] else None,
            transport_factory=lambda p: FakeTransport(p, self.frames, self.flags),
            clock=self.scheduler.clock,
            sensors=Sensors(self.hwmon, self.power, self.scheduler.clock),
        )

    def take(self) -> list[bytes]:
        out = list(self.frames)
        self.frames.clear()
        return out

    def set_cpu_temp(self, celsius: float) -> None:
        chip = self.hwmon / "hwmon0"
        chip.mkdir(exist_ok=True)
        (chip / "name").write_text("coretemp\n")
        (chip / "temp1_input").write_text(f"{int(celsius * 1000)}\n")


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)
