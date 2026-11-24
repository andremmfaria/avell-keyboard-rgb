# Device protocol

Status: first hardware test done on 2026-11-24 on a real ITE 8291 rev 0.02 laptop keyboard. Evidence: `rgb-test-20261124-011715.log` (frame log plus the tester's answers). Each assumption below is marked verified or unverified with that date. The facts come from public protocol descriptions and the test; all constants live in one file, `src/avell_keyboard_rgb/protocol.py`, so a value that turns out to be wrong is a one-file fix. The code was written from these facts, not copied from any GPL driver.

## Device

| Item | Value |
|---|---|
| USB id | `048d:ce00`, "ITE Device(8291)" |
| Revision | bcdDevice 0.02 (4 zone firmware). Revision 0.03 devices with the same id are per-key and are a different protocol |
| Interface | USB interface 1, the vendor HID interface, usage page `0xFF12` |
| Node | `/dev/hidrawN`, found by scanning `/sys/class/hidraw/*/device/uevent` for `HID_ID=0003:0000048D:0000CE00`, skipping nodes whose report descriptor does not contain usage page `06 12 FF` |
| Kernel driver | none to detach; the hidraw node is used directly |

The keys are not individually addressable on this revision. There are 4 zones, numbered 1 to 4 from left to right (verified 2026-11-24, `rgb-test-20261124-011715.log`: zone 1 far left, 2 centre left, 3 centre right, 4 far right, colours correct).

## Transport

Each command is one 8 byte HID feature report with no report ID, sent with the `HIDIOCSFEATURE` ioctl on the hidraw node, using only the standard library (`fcntl.ioctl`). Because the device has no report ID, the buffer handed to the ioctl is 9 bytes: a leading `00` report number (which the kernel strips) followed by the 8 frame bytes. The ioctl request number is `HIDIOCSFEATURE(9) = 0xC0094806`, and a test checks it against the kernel macro. Nothing is ever read back. Verified 2026-11-24 (`rgb-test-20261124-011715.log`): the 9 byte buffer with the leading `00` is accepted and every ioctl returned 9.

## Frames

| Frame | Meaning |
|---|---|
| `14 00 Z R G B 00 00` | Colour definition. `Z` 1 to 4 sets zone colours in direct mode, `Z` 1 to 7 sets the effect palette |
| `08 02 MODE SPEED BRIGHT 08 BEHAV 00` | Mode frame: power on, mode, speed, brightness. Byte 6 is always `08`. `BEHAV` is a direction or behaviour byte. The last byte (the firmware SAVE byte) is always `00` |
| `08 01 00 00 00 00 00 00` | Off |

Modes: direct `01`, breathing `02`, wave `03`, rainbow `05`, raindrop `0a` (unsupported, see below), flashing `12`, gradient `13`. Ranges: brightness 0 to 50, user speed 0 to 10 (higher is faster, see below), direction 0 to 4.

Static colours: four colour frames (`Z` 1 to 4), then the mode frame `08 02 01 05 BRIGHT 08 00 00`. A firmware effect: the palette colour frames (default palette: `ff0000`, `ff1c00`, `ff7700`, `00ff00`, `0000ff`, `00ffff`, `ff00ff`, or the user's own, up to 7), then the mode frame with the effect's mode byte.

## Speed is inverted on the wire

Verified 2026-11-24 (`rgb-test-20261124-011715.log`): wave at wire speed 2 looked faster than at wire speed 5, and wire speed 9 looked slower than that. A higher wire byte means slower. Everything above `protocol.py` (daemon, D-Bus, CLI, GUI) uses a user speed of 0 to 10 where higher is faster, and `mode_frame()` sends `10 - speed`. The inversion is in that one function and nowhere else. The static colour speed byte (`DIRECT_SPEED_WIRE`) is a wire value and is not inverted.

Wire speed 0 is invalid. Verified 2026-11-24 on the installed 0.1.1 package (evidence: user report, no log): user speed 10, which 0.1.1 sent as wire byte 0, made every firmware effect glitch and go static, while user speed 9 (wire 1) worked and was very fast. So wire 1 is the fastest valid value, and `mode_frame()` sends `max(1, 10 - speed)`: user 9 and user 10 both send wire 1 and are the same speed on this firmware. The user facing range stays 0 to 10. The slow end (user 0, wire 10) has not been checked on its own; wire 9 was slow in the first hardware test. The installed hardware test has a speed sweep step to check it (see [../tests/hardware/README.md](../tests/hardware/README.md)).

## Hardware test results (2026-11-24)

Evidence file for every row: `rgb-test-20261124-011715.log`.

| Item | Status | Observed |
|---|---|---|
| 9 byte `HIDIOCSFEATURE` buffer with leading `00` | Verified | All ioctls returned 9 |
| Zone order 1 to 4 | Verified | Far left, centre left, centre right, far right; colours correct |
| Brightness byte | Verified | 0 gives no backlight, 10 < 25 < 50 in brightness |
| Direct mode frame `08 02 01 05 19 08 00 00` | Verified | Lights the zones set by the colour frames |
| Palette frames `14 00 Z R G B` for Z 1 to 7, sent before effects | Verified | Accepted and used by effects |
| Speed inverted on the wire | Verified | See above |
| Wire speed 0 | Verified invalid | Effects glitch and go static (user report 2026-11-24 on installed 0.1.1, no log). Wire 1 works and is the fastest |
| Wire speed 10 (user 0, slowest) | Unverified | Not tested on its own; the speed sweep in the installed hardware test covers it |
| Off frame `08 01 00 00 00 00 00 00` | Verified | Backlight completely off, tester answered y |
| Breathing, flashing, gradient | Verified | Each cycles through the palette colours |
| Wave with `BEHAV` 1 | Verified | Wave of colours moves left to right |
| Wave with `BEHAV` 0, 2, 3, 4 and `BEHAV` on other effects | Unverified | Not tested. Wave defaults to 1 and all other effects to 0; other direction values are accepted but their meaning is unknown |
| Rainbow | Verified, partly understood | Showed red, orange, yellow and green, each on a region. It seems to ignore or only partly use the 7 palette slots; no explanation is claimed |
| Raindrop (`0a`) | Unsupported on rev 0.02 | Nothing happened, the display stayed on the previous rainbow |
| Colour cast needing `COLOR_SCALE` | Unverified | Not examined beyond the primary colours looking right |
| Brightness-only frame `09 02 BRIGHT 00 00 00 00 00` | Unverified | Not tested, not used |
| State kept across suspend | Unverified | Not tested; the daemon re-applies after resume regardless |
| SAVE byte and persist frame (`1a 00 01 04 00 00 00 01`) | Unverified, not implemented | Never sent by the hardware test, so their effect is unknown. They were removed from the code |

## Raindrop

The mode constant stays in `protocol.py` (`MODES`, with `UNSUPPORTED_EFFECTS`) because other revisions may use it. The daemon rejects `raindrop` with `InvalidArgument` unless the request carries the option `allow_unverified=true` (CLI: `--allow-unverified`). It is not in `ListEffects`, the CLI help or the GUI. See [dbus-interface.md](dbus-interface.md).

## What the software never sends

- No opcode other than `14` (colour) and `08` (mode and off); see the frame table above.
- No SAVE byte and no persist frame. Firmware writes are intentionally not implemented, and the earlier experimental save command was removed. Persistence across power cycles is done by the daemon re-applying its own state at boot and after resume, so the firmware flash is never written.
- No firmware update or flashing commands.
- Frames outside the documented ranges: values are clamped in `protocol.py` before they reach the wire. See [safety.md](safety.md).

## Still to check

1. Other wave direction values (`DIRECTION_MIN`, `DIRECTION_MAX`) and the `BEHAV` byte on other effects.
2. A colour cast that needs per channel scaling (`COLOR_SCALE`).
3. Whether suspend keeps the keyboard state.
4. The slow end of the speed range (user 0, wire 10).

If the `tuxedo-drivers` kernel module is loaded for this device it owns the HID device and the two would conflict; unload it or do not install this package (see [hardware.md](hardware.md)).

## Related documentation

- [hardware.md](hardware.md): the same test results in plain language, and the supported revisions.
- [safety.md](safety.md): what the software never sends.
- [dbus-interface.md](dbus-interface.md): how the daemon exposes effects, speed and `allow_unverified`.
- [usage.md](usage.md): the CLI view of speed, direction and effects.
- [development.md](development.md): how to run the hardware test and where constants live.
