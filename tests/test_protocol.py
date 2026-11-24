from __future__ import annotations

import pytest

from avell_keyboard_rgb import protocol


def test_color_frame_layout() -> None:
    assert protocol.color_frame(2, (0x11, 0x22, 0x33)) == bytes.fromhex("1400021122330000")


def test_color_index_range() -> None:
    with pytest.raises(ValueError):
        protocol.color_frame(0, (0, 0, 0))
    with pytest.raises(ValueError):
        protocol.color_frame(8, (0, 0, 0))


def test_color_channels_are_clamped() -> None:
    assert protocol.color_frame(1, (300, -5, 255))[3:6] == bytes([255, 0, 255])


def test_mode_frame_layout_and_no_save_by_default() -> None:
    frame = protocol.mode_frame(0x03, 5, 30, 2)
    assert frame == bytes.fromhex("080203051e080200")
    assert frame[7] == 0x00


def test_mode_frame_clamps() -> None:
    frame = protocol.mode_frame(0x02, 99, 99, 99)
    assert frame[3] == protocol.SPEED_MAX
    assert frame[4] == protocol.BRIGHTNESS_MAX
    assert frame[6] == protocol.DIRECTION_MAX
    low = protocol.mode_frame(0x02, -4, -4)
    assert low[3] == 0 and low[4] == 0


def test_save_byte_only_when_asked() -> None:
    assert protocol.mode_frame(1, 3, 10, save=True)[7] == 0x01


def test_off_frame() -> None:
    assert protocol.off_frame() == bytes.fromhex("0801000000000000")


def test_zone_frames_sequence() -> None:
    frames = protocol.zones_frames([(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)], 25)
    assert len(frames) == 5
    assert frames[0] == bytes.fromhex("1400010102030000")
    assert frames[3] == bytes.fromhex("1400040a0b0c0000")
    assert frames[4] == bytes.fromhex("0802010319080000")


def test_zone_frames_need_four_colours() -> None:
    with pytest.raises(ValueError):
        protocol.zones_frames([(0, 0, 0)] * 3, 10)


@pytest.mark.parametrize("name", protocol.FIRMWARE_EFFECTS)
def test_effect_frames(name: str) -> None:
    frames = protocol.effect_frames(name, 4, 20, [(255, 0, 0), (0, 0, 255)])
    assert len(frames) == 3
    assert frames[-1][2] == protocol.MODES[name]
    assert frames[-1][7] == 0


def test_effect_default_palette_has_seven_entries() -> None:
    assert len(protocol.effect_frames("wave", 5, 20)) == 8


def test_unknown_effect_rejected() -> None:
    with pytest.raises(ValueError):
        protocol.effect_frames("strobe", 1, 1)


def test_known_mode_values() -> None:
    assert protocol.MODES == {
        "breathing": 0x02,
        "wave": 0x03,
        "rainbow": 0x05,
        "raindrop": 0x0A,
        "flashing": 0x12,
        "gradient": 0x13,
    }
    assert protocol.MODE_DIRECT == 0x01


def test_default_builders_never_emit_save_or_persist() -> None:
    frames = protocol.zones_frames([(9, 9, 9)] * 4, 50)
    for name in protocol.FIRMWARE_EFFECTS:
        frames += protocol.effect_frames(name, 10, 50, direction=4)
    frames.append(protocol.off_frame())
    assert all(len(f) == 8 for f in frames)
    assert all(f[0] != 0x1A for f in frames)
    assert all(f[7] == 0 for f in frames if f[0] == protocol.OP_MODE)


def test_persist_frame_value() -> None:
    assert protocol.persist_frame() == bytes.fromhex("1a00010400000001")


def test_parse_and_format_color() -> None:
    assert protocol.parse_color("#FF8000") == (255, 128, 0)
    assert protocol.format_color((255, 128, 0)) == "ff8000"
    for bad in ("fff", "gggggg", "ff80001", ""):
        with pytest.raises(ValueError):
            protocol.parse_color(bad)
