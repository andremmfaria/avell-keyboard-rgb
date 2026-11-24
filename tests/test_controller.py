from __future__ import annotations

import pytest

from avell_keyboard_rgb import protocol
from avell_keyboard_rgb.hidraw import DeviceError
from avell_keyboard_rgb.state import InvalidArgument, ProfileNotFound, StateStore

from .conftest import Rig

MODE_BYTE = 0x08


def modes(frames: list[bytes]) -> list[bytes]:
    return [f for f in frames if f[0] == MODE_BYTE]


def test_set_zones_sends_four_colours_then_direct_mode(rig: Rig) -> None:
    rig.controller.set_zones(["ff0000", "00ff00", "0000ff", "ffffff"])
    frames = rig.take()
    assert frames[0] == bytes.fromhex("140001ff00000000")
    assert frames[1] == bytes.fromhex("14000200ff000000")
    assert frames[2] == bytes.fromhex("1400030000ff0000")
    assert frames[3] == bytes.fromhex("140004ffffff0000")
    assert frames[4][:3] == bytes([0x08, 0x02, 0x01])


def test_zone_validation_does_not_touch_device(rig: Rig) -> None:
    with pytest.raises(InvalidArgument):
        rig.controller.set_zone(5, "ffffff")
    with pytest.raises(InvalidArgument):
        rig.controller.set_zone(1, "nothex")
    with pytest.raises(InvalidArgument):
        rig.controller.set_zones(["ffffff"] * 3)
    with pytest.raises(InvalidArgument):
        rig.controller.set_brightness(51)
    assert rig.take() == []


def test_off_then_on_restores_colours(rig: Rig) -> None:
    rig.controller.set_zones(["010203"] * 4)
    rig.take()
    rig.controller.set_power(False)
    assert rig.take() == [protocol.off_frame()]
    rig.controller.set_power(True)
    assert rig.take()[0] == bytes.fromhex("1400010102030000")


def test_firmware_effect_frames(rig: Rig) -> None:
    rig.controller.set_effect("wave", {"speed": 6, "palette": ["ff0000", "00ff00"]})
    frames = rig.take()
    assert len(frames) == 3
    assert frames[-1][:5] == bytes([0x08, 0x02, 0x03, 10 - 6, rig.controller.state.brightness])
    rig.controller.set_effect("static", {})
    assert rig.take()[-1][2] == protocol.MODE_DIRECT


def test_nothing_ever_sends_save_or_persist(rig: Rig) -> None:
    c = rig.controller
    c.set_zones(["ff0000"] * 4)
    c.set_zone(2, "00ff00")
    c.set_brightness(50)
    for name in protocol.FIRMWARE_EFFECTS:
        c.set_effect(name, {"speed": 10, "direction": 4})
    c.set_power(False)
    c.set_power(True)
    c.start_software_effect("fade", {})
    rig.scheduler.advance(3)
    c.stop_software_effect()
    c.identify_zone(2)
    rig.scheduler.advance(3)
    c.save_profile("p")
    c.load_profile("p")
    frames = rig.take()
    assert frames
    assert all(f[0] != 0x1A for f in frames)
    assert all(f[7] == 0 for f in modes(frames))


def test_software_effect_ticks_at_fps_and_stops_cleanly(rig: Rig) -> None:
    c = rig.controller
    c.start_software_effect("fade", {"fps": 5, "period": 5})
    rig.take()
    rig.scheduler.advance(2.0)
    updates = len(modes(rig.take()))
    assert 8 <= updates <= 11  # about 5 per second for 2 s
    c.stop_software_effect()
    rig.take()
    rig.scheduler.advance(5)
    assert rig.take() == []
    assert not c.snapshot()["software_effect"]


def test_stop_leaves_no_pending_tick(rig: Rig) -> None:
    rig.controller.start_software_effect("fade", {})
    rig.controller.stop_software_effect()
    rig.scheduler.advance(1)
    rig.take()
    rig.scheduler.advance(10)
    assert rig.take() == []


def test_software_effect_paused_while_off_and_resumes(rig: Rig) -> None:
    c = rig.controller
    c.start_software_effect("fade", {"fps": 10, "period": 5})
    c.set_power(False)
    rig.take()
    rig.scheduler.advance(3)
    assert rig.take() == []
    c.set_power(True)
    assert rig.take()  # running again
    assert c.snapshot()["software_effect"] == "fade"


def test_manual_colours_cancel_software_effect(rig: Rig) -> None:
    c = rig.controller
    c.start_software_effect("fade", {})
    c.set_zone(1, "ff0000")
    assert c.snapshot()["software_effect"] == ""
    rig.take()
    rig.scheduler.advance(5)
    assert rig.take() == []


def test_invalid_software_effect_keeps_state(rig: Rig) -> None:
    with pytest.raises(InvalidArgument):
        rig.controller.start_software_effect("fade", {"fps": 99})
    assert rig.controller.state.software is None
    assert rig.take() == []


def test_identify_flashes_then_restores(rig: Rig) -> None:
    c = rig.controller
    c.set_zones(["112233"] * 4)
    rig.take()
    c.identify_zone(3)
    first = rig.take()
    assert first[2][3:6] == bytes([255, 255, 255])  # zone 3 white
    assert first[0][3:6] == bytes([0, 0, 0])
    rig.scheduler.advance(2)
    frames = rig.take()
    assert frames[-5][3:6] == bytes([0x11, 0x22, 0x33])  # original colours restored last
    assert rig.scheduler.pending <= 1


def test_profiles_roundtrip_through_controller(rig: Rig) -> None:
    c = rig.controller
    c.set_zones(["aa0000", "00aa00", "0000aa", "aaaaaa"])
    c.set_brightness(33)
    c.save_profile("night")
    c.set_zones(["000000"] * 4)
    c.load_profile("night")
    assert c.state.zones[0] == "aa0000" and c.state.brightness == 33
    assert c.list_profiles() == ["night"]
    c.delete_profile("night")
    with pytest.raises(ProfileNotFound):
        c.load_profile("night")


def test_state_persists_and_reapplies_on_startup(rig: Rig) -> None:
    rig.controller.set_zones(["abcdef"] * 4)
    rig.controller.set_brightness(7)
    rig.controller.flush()
    rig.take()
    from avell_keyboard_rgb.controller import Controller

    second = Controller(
        StateStore(rig.store.directory),
        rig.scheduler,
        finder=rig.controller._finder,
        transport_factory=rig.controller._factory,
    )
    second.startup()
    frames = rig.take()
    assert frames[0] == bytes.fromhex("140001abcdef0000")
    assert frames[-1][4] == 7


def test_persist_is_debounced(rig: Rig) -> None:
    c = rig.controller
    for i in range(20):
        c.set_brightness(i)
    assert not rig.store.state_file.exists()
    rig.scheduler.advance(1.5)
    assert rig.store.load().brightness == 19


def test_missing_device_stores_state_and_retries(rig: Rig) -> None:
    rig.flags["present"] = False
    with pytest.raises(DeviceError):
        rig.controller.set_zones(["010101"] * 4)
    assert not rig.controller.connected
    assert rig.controller.state.zones == ["010101"] * 4
    rig.flags["present"] = True
    rig.scheduler.advance(6)
    assert rig.controller.connected
    assert rig.take()[0] == bytes.fromhex("1400010101010000")


def test_write_failure_then_recovery_reapplies(rig: Rig) -> None:
    c = rig.controller
    c.set_zones(["020202"] * 4)
    rig.take()
    rig.flags["fail"] = True
    with pytest.raises(DeviceError):
        c.set_brightness(9)
    assert not c.connected and "simulated" in c.last_error
    rig.flags["fail"] = False
    rig.scheduler.advance(6)
    assert c.connected
    frames = rig.take()
    assert frames[-1][4] == 9


def test_resume_reapply(rig: Rig) -> None:
    rig.controller.set_zones(["030303"] * 4)
    rig.take()
    rig.controller.reapply()  # what the logind resume hook calls
    assert len(rig.take()) == 5


def test_listeners_notified(rig: Rig) -> None:
    seen: list[int] = []
    rig.controller.listeners.append(lambda: seen.append(1))
    rig.controller.set_power(False)
    assert seen


def test_hand_edited_bad_software_effect_dropped(rig: Rig) -> None:
    import json

    rig.store.state_file.parent.mkdir(parents=True, exist_ok=True)
    rig.store.state_file.write_text(
        json.dumps({"software": {"name": "fade", "options": {"fps": 500}}})
    )
    from avell_keyboard_rgb.controller import Controller

    c = Controller(rig.store, rig.scheduler, finder=lambda: None)
    assert c.state.software is None
