# Hardware

## Supported hardware

Only the ITE 8291 keyboard controller, USB id `048d:ce00`, with bcdDevice 0.02. This firmware has 4 colour zones. Keys are not individually addressable, and there is no per-key mode in this project. The device is found through its hidraw node; see [protocol.md](protocol.md) for how.

Check the revision before installing:

```text
lsusb -v -d 048d:ce00 | grep bcdDevice
```

## Unsupported devices

- Devices with the same id but bcdDevice 0.03 are per-key keyboards that use a different protocol. They are not supported, and this software does not check the revision for you: it matches on the USB id and the vendor usage page only. Check it yourself before installing.
- Other ITE controllers (`048d:8910`, `048d:8297`, `048d:600b` and so on) are not supported.
- Not compatible with the `tuxedo-drivers` `ite_8291` kernel module being loaded for the same device: both would own the HID device. Unload the module or do not install this package.

## Hardware test results

Tested on 2026-11-24 on one real ITE 8291 rev 0.02 laptop keyboard, with log `rgb-test-20261124-011715.log`. The test suite itself uses a fake keyboard, so these results are the only evidence from hardware. The per-item evidence is in [protocol.md](protocol.md).

Works:

- Four zone colours, with zones 1 to 4 running far left to far right.
- Brightness 0 to 50, where 0 is no backlight, and the off frame.
- Breathing, flashing and gradient, each cycling through the palette colours.
- Wave, moving left to right with the default direction.
- Palette colours for effects.
- Speed. It is inverted in the firmware; the software hides this, so you set 0 to 10 and higher is faster.

Known limits:

- Wire speed 0 is invalid: effects glitch and stop. The software never sends it, so speed 9 and 10 run at the same speed (found on the installed 0.1.1 package, by user report, no log). See [usage.md](usage.md).
- Rainbow works but showed only red, orange, yellow and green on regions, so it seems not to use all 7 palette colours. This is not explained.
- Raindrop did nothing on this revision, so it is not offered. The daemon refuses it unless you pass `--allow-unverified` (CLI) or the `allow_unverified` option (D-Bus).

## Not tested yet

- Wave directions other than left to right, and the direction byte on the other effects.
- Behaviour across suspend and resume (the daemon re-applies the state after resume regardless).
- The slow end of the speed range (user 0, wire 10) on its own, and whether user 9 and 10 look identical. The speed sweep step of the installed hardware test covers this.
- The brightness-only frame and any colour cast of the zone colours.
- Whether the keyboard re-enumerates on the USB bus in ways other than suspend.
- The GUI on screen, and installs on a Fedora family system.

The open items and their status are tracked in [todo.md](../todo.md). The script used to test the installed package is described in [../tests/hardware/README.md](../tests/hardware/README.md).

## Related documentation

- [protocol.md](protocol.md): frames, evidence and the verified and unverified table.
- [usage.md](usage.md): how the limits show up in the CLI and GUI.
- [safety.md](safety.md): what is sent to the device.
- [install.md](install.md): installing after checking the revision.
- [development.md](development.md): running the hardware test script.
- [troubleshooting.md](troubleshooting.md): what to do when the keyboard is not found.
