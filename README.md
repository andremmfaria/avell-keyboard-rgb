<p align="center"><img src="deploy/io.github.andremmfaria.AvellRgbGui.svg" alt="avell-keyboard-rgb logo: four glowing backlight zones" width="128" height="128"></p>

<h1 align="center">avell-keyboard-rgb</h1>

A daemon, command line tool and GTK4 GUI for the 4 zone keyboard backlight of the ITE 8291 controller (USB `048d:ce00`, bcdDevice 0.02) found in some Avell and Clevo/Tongfang laptops. It is an independent, unofficial project, not affiliated with or endorsed by Avell, ITE or Clevo. Product names are used only to identify the hardware this software works with.

Status: version 0.1.1, written from published protocol descriptions. The frames were checked on a real ITE 8291 rev 0.02 keyboard on 2026-11-24 (static zones, brightness, off, speed, most effects); see [docs/protocol.md](docs/protocol.md) for what is verified and what is not. The test suite itself uses a fake keyboard.

## What it does

- Four independent zone colours, brightness 0 to 50, on and off.
- Firmware effects: breathing, wave, rainbow, flashing, gradient, with speed (0 to 10, higher is faster), direction and a palette of up to 7 colours.
- Software effects run by the daemon (rate limited, default 10 updates a second, never more than 20): `cpu-temp` (keyboard colour follows CPU temperature), `battery` (the 4 zones are a charge bar), `fade` (slow colour cycle across the zones).
- Named profiles, kept in `/var/lib/avell-keyboard-rgb/profiles`.
- The daemon re-applies the stored state at start, after resume from suspend, and retries every 5 seconds while the keyboard is missing.
- A "flash this zone" button to see which zone is which.

## Hardware support limits

- Only the ITE 8291 `048d:ce00` with bcdDevice 0.02 (check with `lsusb -v -d 048d:ce00 | grep bcdDevice`). This firmware has 4 colour zones. Keys are not individually addressable, and there is no per-key mode in this project.
- Devices with the same id but bcdDevice 0.03 are per-key keyboards that use a different protocol. They are not supported, and this software does not check the revision for you.
- Other ITE controllers (`048d:8910`, `048d:8297`, `048d:600b` and so on) are not supported.
- Not compatible with the `tuxedo-drivers` `ite_8291` kernel module being loaded for the same device.

## Hardware test results

Tested on 2026-11-24 on one real ITE 8291 rev 0.02 laptop keyboard (log: `rgb-test-20261124-011715.log`, details in [docs/protocol.md](docs/protocol.md)):

- Works: four zone colours (zones 1 to 4 are far left to far right), brightness 0 to 50 (0 is off), off, breathing, flashing, gradient, wave (left to right with the default direction), palette colours.
- Speed is inverted in the firmware. The software hides this: you set 0 to 10, higher is faster.
- Rainbow works but showed only red, orange, yellow and green on regions, so it seems not to use all 7 palette colours. Not explained.
- Raindrop did nothing on this revision, so it is not offered. The daemon refuses it unless you pass `--allow-unverified` (CLI) or the `allow_unverified` option (D-Bus).
- Not tested: wave directions other than left to right, behaviour across suspend.

## Safety notes

- The daemon sends only the documented frames (see [docs/protocol.md](docs/protocol.md)) and clamps every value to the documented range.
- It never writes to the keyboard firmware. Saving state into the firmware is intentionally not implemented, and the mode frame's save byte is always 0.
- No firmware flashing code exists in this project.
- The keyboard forgets its state at power off, and the daemon restores it.

## Install

Packages for Debian family and Fedora family systems are attached to each [release](https://github.com/andremmfaria/avell-keyboard-rgb/releases). They are architecture independent.

```text
sudo apt install ./avell-keyboard-rgb_<version>_all.deb
sudo dnf install ./avell-keyboard-rgb-<version>-1.noarch.rpm
```

Runtime dependencies (also declared in the packages):

| | Debian, Ubuntu (24.04 or newer) | Fedora |
|---|---|---|
| Python 3.10 or newer | `python3` | `python3` |
| PyGObject | `python3-gi` | `python3-gobject` |
| GTK 4 | `gir1.2-gtk-4.0` | `gtk4` |
| libadwaita 1.5 or newer | `gir1.2-adw-1` | `libadwaita` |
| D-Bus | `dbus` | `dbus-daemon` |
| polkit | `polkitd` (older: `policykit-1`) | `polkit` |
| systemd and udev | `systemd`, `udev` | `systemd` |

Install layout: the Python code goes to `/usr/lib/avell-keyboard-rgb/avell_keyboard_rgb`, and the launchers in `/usr/bin` (`avell-rgb`, `avell-rgbd`, `avell-rgb-gui`) put that directory on `PYTHONPATH` and run `/usr/bin/python3`. A private directory is used because the distributions disagree about where architecture independent Python code goes (`dist-packages` on Debian, a Python version specific `site-packages` on Fedora), and a private directory keeps one package working across Python releases up to 3.14. It also means pip is never involved, so PEP 668 "externally managed environment" does not apply.

The package installs a system user `avell-rgb` (sysusers.d), a udev rule giving that group access to the keyboard's hidraw node with mode 0660 (never world-writable), a systemd unit with sandboxing, a D-Bus policy and a polkit action. The daemon starts when the keyboard appears (udev) or when a client calls it (D-Bus activation).

Authorisation: anyone can read the state. Changing the keyboard needs the polkit action `io.github.andremmfaria.AvellRgb.control`, which is allowed without a prompt for a local session that is active, and denied for others.

## Use

```text
avell-rgb set ff0000 00ff00 0000ff ffffff    # four zones, left to right
avell-rgb zone 2 ff8800
avell-rgb brightness 30
avell-rgb effect wave --speed 8     # 0 to 10, higher is faster
avell-rgb effect static
avell-rgb off
avell-rgb profile save work
avell-rgb profile load work
avell-rgb software-effect start cpu-temp
avell-rgb software-effect stop
avell-rgb identify 3
avell-rgb status
avell-rgb-gui
```

`avell-rgb --help` lists everything; there is no separate man page yet.

## Troubleshooting

If every command that changes the keyboard says "not authorized" while `avell-rgb status` works, check the daemon log with `journalctl -u avell-rgbd` for polkit errors. The message "Only trusted callers (e.g. uid 0 or an action owner) can use CheckAuthorization() for subjects belonging to other identities" means the installed polkit policy lacks the `org.freedesktop.policykit.owner` annotation naming the daemon user `avell-rgb`. Version 0.1.1 and newer ship it; upgrade the package. Without that error, the caller is probably not in an active local session, which the polkit action denies by default.

## Develop

```text
uv venv --system-site-packages --python /usr/bin/python3 .venv    # PyGObject comes from the distribution
uv pip install --python .venv/bin/python pytest ruff mypy
uv pip install --python .venv/bin/python --no-deps -e .
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy src tests
xvfb-run -a .venv/bin/pytest
deploy/check-deploy.sh
```

Run the daemon on a private session bus without a keyboard or root: `avell-rgbd --bus session --no-polkit --state-dir /tmp/avell-state` (it will report the keyboard as not found and retry).

Layout: `protocol.py` (all wire constants and frame builders), `hidraw.py` (device discovery and the ioctl), `state.py` (state model and profile store), `effects.py` (software effects engine), `controller.py` (daemon logic without D-Bus), `dbus_service.py` and `daemon.py` (the system service), `dbus_client.py`, `cli.py` and `gui/` (clients). The D-Bus contract is in [docs/dbus-interface.md](docs/dbus-interface.md).

## Licence

MIT, see [LICENSE](LICENSE).
