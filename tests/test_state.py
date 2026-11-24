from __future__ import annotations

import json
from pathlib import Path

import pytest

from avell_keyboard_rgb.state import (
    InvalidArgument,
    ProfileNotFound,
    State,
    StateStore,
    norm_effect,
)


def test_defaults_when_missing(tmp_path: Path) -> None:
    assert StateStore(tmp_path).load() == State()


def test_roundtrip(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    s = State(power=False, brightness=12, zones=["ff0000", "00ff00", "0000ff", "010203"])
    s.effect = norm_effect("wave", {"speed": 7, "palette": ["#FF0000"]})
    store.save(s)
    loaded = store.load()
    assert loaded == s
    assert loaded.effect is not None and loaded.effect["palette"] == ["ff0000"]


def test_corrupt_file_is_moved_aside(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.state_file.write_text("{not json")
    assert store.load() == State()
    assert store.state_file.with_suffix(".bad").exists()


def test_out_of_range_stored_value_falls_back(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.state_file.write_text(json.dumps({"brightness": 500}))
    assert store.load() == State()


def test_profiles(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    s = State(brightness=40)
    store.save_profile("work", s)
    store.save_profile("night.mode-2", s)
    assert store.list_profiles() == ["night.mode-2", "work"]
    assert store.load_profile("work").brightness == 40
    store.delete_profile("work")
    assert store.list_profiles() == ["night.mode-2"]
    with pytest.raises(ProfileNotFound):
        store.load_profile("work")
    with pytest.raises(ProfileNotFound):
        store.delete_profile("work")


@pytest.mark.parametrize("name", ["", ".hidden", "../x", "a/b", "a b", "x" * 65, "é"])
def test_bad_profile_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(InvalidArgument):
        StateStore(tmp_path).save_profile(name, State())


@pytest.mark.parametrize(
    ("name", "opts"),
    [
        ("nope", {}),
        ("wave", {"speed": 11}),
        ("wave", {"speed": True}),
        ("wave", {"direction": 5}),
        ("wave", {"palette": ["ff0000"] * 8}),
        ("wave", {"palette": ["zzzzzz"]}),
        ("wave", {"colour": 1}),
    ],
)
def test_effect_validation(name: str, opts: dict) -> None:  # type: ignore[type-arg]
    with pytest.raises(InvalidArgument):
        norm_effect(name, opts)


def test_state_file_is_atomic_and_leaves_no_temp(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save(State())
    store.save(State(brightness=3))
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]


def test_raindrop_rejected_without_flag() -> None:
    with pytest.raises(InvalidArgument, match="unsupported"):
        norm_effect("raindrop", {})
    with pytest.raises(InvalidArgument):
        norm_effect("raindrop", {"allow_unverified": False})


def test_raindrop_allowed_with_flag_and_survives_reload() -> None:
    effect = norm_effect("raindrop", {"allow_unverified": True})
    assert effect["allow_unverified"] is True
    assert State.from_dict(State(effect=effect).to_dict()).effect == effect


def test_allow_unverified_must_be_boolean() -> None:
    with pytest.raises(InvalidArgument):
        norm_effect("wave", {"allow_unverified": 1})


def test_wave_default_direction_is_left_to_right() -> None:
    assert norm_effect("wave", {})["direction"] == 1
    assert norm_effect("breathing", {})["direction"] == 0
