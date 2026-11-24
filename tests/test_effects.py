from __future__ import annotations

from pathlib import Path

import pytest

from avell_keyboard_rgb.effects import (
    Sensors,
    SoftwareEffectEngine,
    create_effect,
    ramp,
)
from avell_keyboard_rgb.state import InvalidArgument

from .conftest import FakeScheduler


def make(tmp_path: Path, name: str, options: dict) -> tuple:  # type: ignore[type-arg]
    clock = FakeScheduler()
    hw, pw = tmp_path / "hw", tmp_path / "pw"
    hw.mkdir(exist_ok=True)
    pw.mkdir(exist_ok=True)
    frames: list = []  # type: ignore[type-arg]
    engine = SoftwareEffectEngine(
        frames.append, clock=clock.clock, sensors=Sensors(hw, pw, clock.clock)
    )
    engine.start(name, options)
    return engine, clock, frames, hw, pw


def test_rate_limit_and_dedupe(tmp_path: Path) -> None:
    engine, clock, frames, _, _ = make(tmp_path, "fade", {"fps": 10, "period": 10})
    assert engine.tick() is True
    assert engine.tick() is False  # same instant
    clock.advance(0.05)
    assert engine.tick() is False  # below 100 ms interval
    clock.advance(0.05)
    assert engine.tick() is True
    assert len(frames) == 2


def test_frames_per_second_never_exceed_fps(tmp_path: Path) -> None:
    engine, clock, frames, _, _ = make(tmp_path, "fade", {"fps": 5, "period": 5})
    for _ in range(1000):  # a busy caller ticking every millisecond for 1 s
        engine.tick()
        clock.advance(0.001)
    assert len(frames) <= 6


def test_unchanged_frame_is_not_resent(tmp_path: Path) -> None:
    engine, clock, frames, hw, _ = make(tmp_path, "cpu-temp", {})
    chip = hw / "hwmon0"
    chip.mkdir()
    (chip / "name").write_text("coretemp")
    (chip / "temp1_input").write_text("50000")
    engine.tick()
    for _ in range(5):
        clock.advance(0.2)
        engine.tick()
    assert len(frames) == 1
    (chip / "temp1_input").write_text("90000")
    clock.advance(1.5)  # sensor cache expires
    engine.tick()
    assert len(frames) == 2
    assert frames[-1] == [(255, 0, 0)] * 4


def test_cpu_temp_colours(tmp_path: Path) -> None:
    engine, clock, frames, hw, _ = make(tmp_path, "cpu-temp", {"min_temp": 40, "max_temp": 90})
    chip = hw / "hwmon0"
    chip.mkdir()
    (chip / "name").write_text("k10temp")
    (chip / "temp1_input").write_text("30000")
    engine.tick()
    assert frames[-1] == [(0, 255, 0)] * 4


def test_cpu_temp_missing_sensor_shows_blue(tmp_path: Path) -> None:
    engine, _, frames, _, _ = make(tmp_path, "cpu-temp", {})
    engine.tick()
    assert frames == [[(0, 0, 255)] * 4]


@pytest.mark.parametrize(
    ("percent", "expected"),
    [
        (100, [(0, 255, 0)] * 4),
        (60, [(0, 255, 0)] * 3 + [(0, 0, 0)]),
        (30, [(255, 160, 0)] * 2 + [(0, 0, 0)] * 2),
        (5, [(255, 0, 0)] + [(0, 0, 0)] * 3),
    ],
)
def test_battery_bar(tmp_path: Path, percent: int, expected: list) -> None:  # type: ignore[type-arg]
    engine, _, frames, _, pw = make(tmp_path, "battery", {})
    bat = pw / "BAT0"
    bat.mkdir()
    (bat / "capacity").write_text(str(percent))
    (bat / "status").write_text("Discharging")
    engine.tick()
    assert frames[-1] == expected


def test_battery_charging_pulses_top_lit_zone(tmp_path: Path) -> None:
    engine, clock, frames, _, pw = make(tmp_path, "battery", {"fps": 20})
    bat = pw / "BAT0"
    bat.mkdir()
    (bat / "capacity").write_text("50")
    (bat / "status").write_text("Charging")
    for _ in range(40):
        engine.tick()
        clock.advance(0.05)
    assert len({f[1] for f in frames}) > 3
    assert all(f[0] == (0, 255, 0) for f in frames)


def test_fade_moves_across_zones(tmp_path: Path) -> None:
    engine, clock, frames, _, _ = make(
        tmp_path, "fade", {"period": 4, "colors": ["ff0000", "00ff00", "0000ff"]}
    )
    engine.tick()
    assert len(set(frames[0])) >= 3  # zones differ
    clock.advance(2)
    engine.tick()
    assert frames[1] != frames[0]


def test_stop_halts_output(tmp_path: Path) -> None:
    engine, clock, frames, _, _ = make(tmp_path, "fade", {})
    engine.tick()
    engine.stop()
    clock.advance(5)
    assert engine.tick() is False
    assert not engine.running
    assert len(frames) == 1


@pytest.mark.parametrize(
    ("name", "opts"),
    [
        ("nope", {}),
        ("fade", {"fps": 0}),
        ("fade", {"fps": 21}),
        ("fade", {"period": 1}),
        ("fade", {"colors": []}),
        ("fade", {"bogus": 1}),
        ("cpu-temp", {"min_temp": 90, "max_temp": 40}),
        ("battery", {"x": 1}),
    ],
)
def test_option_validation(name: str, opts: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(InvalidArgument):
        create_effect(name, opts)


def test_ramp() -> None:
    assert ramp([(0, 0, 0), (100, 0, 0)], 0.5) == (50, 0, 0)
    assert ramp([(0, 0, 0), (100, 0, 0)], 2.0) == (100, 0, 0)
    assert ramp([(0, 0, 0), (100, 0, 0)], 1.0, wrap=True) == (0, 0, 0)
