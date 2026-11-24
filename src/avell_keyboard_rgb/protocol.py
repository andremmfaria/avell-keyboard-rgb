"""ITE 8291 rev 0.02 (048d:ce00) wire protocol: every constant and frame builder lives here.

Status: first hardware test done on 2026-11-24 (evidence: rgb-test-20261124-011715.log).
docs/protocol.md lists what was verified and what is still unverified. This is the
only module that knows wire values, including the speed inversion. Nothing here
touches the device.

The code is written from the protocol description, not copied from any GPL driver.
"""

from __future__ import annotations

from collections.abc import Sequence

# --- device identity -------------------------------------------------------
USB_VENDOR_ID = 0x048D
USB_PRODUCT_ID = 0xCE00
# Text found in /sys/class/hidraw/hidrawN/device/uevent for the right device.
HID_ID_STRING = "HID_ID=0003:0000048D:0000CE00"
# Vendor interface 1 declares this usage page; used to skip other interfaces.
USAGE_PAGE = 0xFF12
# Short item "Usage Page (16 bit)" = 0x06, then the page little endian.
USAGE_PAGE_DESCRIPTOR_BYTES = bytes([0x06, USAGE_PAGE & 0xFF, USAGE_PAGE >> 8])

# --- transport -------------------------------------------------------------
FRAME_LENGTH = 8
# The device has no report ID. hidraw wants a leading report number byte in the
# buffer; for "no report ID" that byte is 0x00 and the kernel strips it.
REPORT_ID_PREFIX = b"\x00"

# --- value ranges ----------------------------------------------------------
ZONE_COUNT = 4
PALETTE_SIZE = 7
BRIGHTNESS_MIN = 0
BRIGHTNESS_MAX = 50
SPEED_MIN = 0
SPEED_MAX = 10
DIRECTION_MIN = 0
DIRECTION_MAX = 4
# Verified 2026-11-24: on the wire a larger speed byte is SLOWER. Callers use
# 0..10 where higher is faster; mode_frame() sends SPEED_MAX - speed.
# Per channel scale (numerator over 255) for panels with a colour cast.
COLOR_SCALE = (255, 255, 255)

# --- opcodes ---------------------------------------------------------------
OP_COLOR = 0x14
OP_MODE = 0x08
# Power state byte of the mode frame.
POWER_OFF = 0x01
POWER_ON = 0x02
# Fixed seventh byte of the mode frame.
MODE_FIXED_BYTE = 0x08
# Last byte of the mode frame. Always 0: firmware writes are not implemented.
MODE_SAVE_BYTE = 0x00

# --- modes -----------------------------------------------------------------
MODE_DIRECT = 0x01
MODES: dict[str, int] = {
    "breathing": 0x02,
    "wave": 0x03,
    "rainbow": 0x05,
    "raindrop": 0x0A,
    "flashing": 0x12,
    "gradient": 0x13,
}
# Raindrop (0x0A) did nothing on rev 0.02: the display stayed on the previous
# effect (hardware test 2026-11-24). The constant stays for other revisions.
# The daemon rejects it unless the caller passes allow_unverified.
UNSUPPORTED_EFFECTS: tuple[str, ...] = ("raindrop",)
FIRMWARE_EFFECTS: tuple[str, ...] = tuple(n for n in MODES if n not in UNSUPPORTED_EFFECTS)
# BEHAV byte 1 on wave moves left to right (verified). Other values 0..4 and the
# BEHAV byte on other effects are unverified.
WAVE_LEFT_TO_RIGHT = 1
# Wire speed byte for static colours; 5 is what the hardware test sent.
DIRECT_SPEED_WIRE = 5

# Default effect palette (red, orange, yellow, green, blue, teal, purple).
DEFAULT_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0xFF, 0x00, 0x00),
    (0xFF, 0x1C, 0x00),
    (0xFF, 0x77, 0x00),
    (0x00, 0xFF, 0x00),
    (0x00, 0x00, 0xFF),
    (0x00, 0xFF, 0xFF),
    (0xFF, 0x00, 0xFF),
)

RGB = tuple[int, int, int]
Frame = bytes


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def _scale(rgb: RGB) -> RGB:
    r, g, b = (clamp(c, 0, 255) for c in rgb)
    sr, sg, sb = COLOR_SCALE
    return (r * sr // 255, g * sg // 255, b * sb // 255)


def parse_color(text: str) -> RGB:
    """Parse 'rrggbb' or '#rrggbb'. Raises ValueError on anything else."""
    value = text.strip().lstrip("#")
    if len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError(f"invalid colour {text!r}, expected rrggbb")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def format_color(rgb: RGB) -> str:
    return "{:02x}{:02x}{:02x}".format(*(clamp(c, 0, 255) for c in rgb))


def _frame(*data: int) -> Frame:
    frame = bytes(data)
    if len(frame) != FRAME_LENGTH:
        raise ValueError("frame must be 8 bytes")
    return frame


def color_frame(index: int, rgb: RGB) -> Frame:
    """Colour definition. Index 1..4 are zones in direct mode, 1..7 the effect palette."""
    if not 1 <= index <= max(ZONE_COUNT, PALETTE_SIZE):
        raise ValueError(f"colour index {index} out of range")
    r, g, b = _scale(rgb)
    return _frame(OP_COLOR, 0x00, index, r, g, b, 0x00, 0x00)


def mode_frame(
    mode: int,
    speed: int,
    brightness: int,
    behaviour: int = 0,
) -> Frame:
    """Mode frame: 08 02 MODE SPEED BRIGHT 08 BEHAV 00. The last byte is always 0.

    `speed` is the user value, 0..10, higher is faster; it is inverted on the wire.
    """
    # User speed 0..10 (higher is faster) -> wire byte (higher is slower).
    speed = SPEED_MAX - clamp(speed, SPEED_MIN, SPEED_MAX)
    return _frame(
        OP_MODE,
        POWER_ON,
        mode,
        speed,
        clamp(brightness, BRIGHTNESS_MIN, BRIGHTNESS_MAX),
        MODE_FIXED_BYTE,
        clamp(behaviour, DIRECTION_MIN, DIRECTION_MAX),
        MODE_SAVE_BYTE,
    )


def off_frame() -> Frame:
    return _frame(OP_MODE, POWER_OFF, 0, 0, 0, 0, 0, 0)


def default_direction(name: str) -> int:
    """BEHAV default: left to right for wave (verified), 0 for everything else."""
    return WAVE_LEFT_TO_RIGHT if name == "wave" else 0


def zones_frames(colors: Sequence[RGB], brightness: int) -> list[Frame]:
    """Frames for a static 4 zone image: four colour frames, then direct mode."""
    if len(colors) != ZONE_COUNT:
        raise ValueError(f"expected {ZONE_COUNT} colours, got {len(colors)}")
    frames = [color_frame(i + 1, rgb) for i, rgb in enumerate(colors)]
    frames.append(mode_frame(MODE_DIRECT, SPEED_MAX - DIRECT_SPEED_WIRE, brightness))
    return frames


def effect_frames(
    name: str,
    speed: int,
    brightness: int,
    palette: Sequence[RGB] | None = None,
    direction: int | None = None,
) -> list[Frame]:
    """Frames for a firmware effect: palette colour frames, then the mode frame."""
    if name not in MODES:
        raise ValueError(f"unknown firmware effect {name!r}")
    colors = list(palette) if palette else list(DEFAULT_PALETTE)
    if not 1 <= len(colors) <= PALETTE_SIZE:
        raise ValueError(f"palette needs 1 to {PALETTE_SIZE} colours")
    frames = [color_frame(i + 1, rgb) for i, rgb in enumerate(colors)]
    if direction is None:
        direction = default_direction(name)
    frames.append(mode_frame(MODES[name], speed, brightness, direction))
    return frames
