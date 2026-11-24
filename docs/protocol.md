# Device protocol

Status: UNVERIFIED on real hardware. Everything below comes from public protocol descriptions of the ITE 8291 rev 0.02 firmware, and no frame has been sent to a real keyboard by this project yet. All constants live in one file, `src/avell_keyboard_rgb/protocol.py`, so a value that turns out to be wrong after the first hardware test is a one-file fix. The code was written from these facts, not copied from any GPL driver.

## Device

| Item | Value |
|---|---|
| USB id | `048d:ce00`, "ITE Device(8291)" |
| Revision | bcdDevice 0.02 (4 zone firmware). Revision 0.03 devices with the same id are per-key and are a different protocol |
| Interface | USB interface 1, the vendor HID interface, usage page `0xFF12` |
| Node | `/dev/hidrawN`, found by scanning `/sys/class/hidraw/*/device/uevent` for `HID_ID=0003:0000048D:0000CE00`, skipping nodes whose report descriptor does not contain usage page `06 12 FF` |
| Kernel driver | none to detach; the hidraw node is used directly |

The keys are not individually addressable on this revision. There are 4 zones, numbered 1 to 4 from left to right (zone order on the physical keyboard is to be confirmed).

## Transport

Each command is one 8 byte HID feature report with no report ID, sent with the `HIDIOCSFEATURE` ioctl on the hidraw node, using only the standard library (`fcntl.ioctl`). Because the device has no report ID, the buffer handed to the ioctl is 9 bytes: a leading `00` report number (which the kernel strips) followed by the 8 frame bytes. The ioctl request number is `HIDIOCSFEATURE(9) = 0xC0094806`, and a test checks it against the kernel macro. Nothing is ever read back.

## Frames

| Frame | Meaning |
|---|---|
| `14 00 Z R G B 00 00` | Colour definition. `Z` 1 to 4 sets zone colours in direct mode, `Z` 1 to 7 sets the effect palette |
| `08 02 MODE SPEED BRIGHT 08 BEHAV SAVE` | Mode frame: power on, mode, speed, brightness. Byte 6 is always `08`. `BEHAV` is a direction or behaviour byte. `SAVE` is always `00` unless the explicit firmware save is used |
| `08 01 00 00 00 00 00 00` | Off |
| `1a 00 01 04 00 00 00 01` | Persist frame. Only sent by the experimental save command |

Modes: direct `01`, breathing `02`, wave `03`, rainbow `05`, raindrop `0a`, flashing `12`, gradient `13`. Ranges: brightness 0 to 50, speed 0 to 10, direction 0 to 4 (the meaning of direction values is inconsistent between sources and unverified).

Static colours: four colour frames (`Z` 1 to 4), then the mode frame `08 02 01 03 BRIGHT 08 00 00`. A firmware effect: the palette colour frames (default palette: red, orange, yellow, green, blue, teal, purple, or the user's own, up to 7), then the mode frame with the effect's mode byte.

## What the software never sends

- No opcode other than the four above.
- No SAVE byte and no persist frame unless the user runs `avell-rgb save --confirm` (D-Bus `ExperimentalSaveToFirmware`). Persistence across power cycles is otherwise done by the daemon re-applying its own state at boot and after resume, so the firmware flash is not written on every change.
- No firmware update or flashing commands.
- Frames outside the documented ranges: values are clamped in `protocol.py` before they reach the wire. Out of range brightness has been reported to wedge a different ITE chip.

## Values to check in the first hardware test

1. Does a static colour frame sequence change the zones, and is the zone order left to right?
2. Is the leading `00` report number correct for the hidraw ioctl, or does the device want the 8 bytes without it? (`REPORT_ID_PREFIX`)
3. Does the speed number run fast to slow or slow to fast? (`INVERT_SPEED`)
4. Are the wave direction values 0 to 4, 1 to 4, or 0 and 1? (`DIRECTION_MIN`, `DIRECTION_MAX`)
5. Is there a colour cast that needs per channel scaling? (`COLOR_SCALE`)
6. Do brightness changes need the full mode frame or does the device accept the brightness-only frame `09 02 BRIGHT 00 00 00 00 00`? The software uses the mode frame, which is the documented path.
7. Does the keyboard keep its state across suspend, so that the re-apply on resume is only a safety net?

If the `tuxedo-drivers` kernel module is loaded for this device it owns the HID device and the two would conflict; unload it or do not install this package.
