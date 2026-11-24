# avell-keyboard-rgb

A daemon, command line tool and GTK4 GUI for the 4 zone keyboard backlight of the ITE 8291 controller (USB `048d:ce00`, bcdDevice 0.02) found in some Avell and Clevo/Tongfang laptops. It is an independent, unofficial project, not affiliated with or endorsed by Avell, ITE or Clevo. Product names are used only to identify the hardware this software works with.

Status: version 0.1.0, written from published protocol descriptions and tested only against a fake keyboard. It has not been run on a real keyboard yet, see [docs/protocol.md](docs/protocol.md) for what the first hardware test should confirm.

## What it does

- Four independent zone colours, brightness 0 to 50, on and off.
- Firmware effects: breathing, wave, rainbow, raindrop, flashing, gradient, with speed, direction and a palette of up to 7 colours.
- Software effects run by the daemon (rate limited, default 10 updates a second, never more than 20): `cpu-temp` (keyboard colour follows CPU temperature), `battery` (the 4 zones are a charge bar), `fade` (slow colour cycle across the zones).
- Named profiles, kept in `/var/lib/avell-keyboard-rgb/profiles`.
- The daemon re-applies the stored state at start, after resume from suspend, and retries every 5 seconds while the keyboard is missing.
- A "flash this zone" button to see which zone is which.

## Hardware support limits

- Only the ITE 8291 `048d:ce00` with bcdDevice 0.02 (check with `lsusb -v -d 048d:ce00 | grep bcdDevice`). This firmware has 4 colour zones. Keys are not individually addressable, and there is no per-key mode in this project.
- Devices with the same id but bcdDevice 0.03 are per-key keyboards that use a different protocol. They are not supported, and this software does not check the revision for you.
- Other ITE controllers (`048d:8910`, `048d:8297`, `048d:600b` and so on) are not supported.
- Not compatible with the `tuxedo-drivers` `ite_8291` kernel module being loaded for the same device.

## Safety notes

- The daemon sends only the documented frames (see [docs/protocol.md](docs/protocol.md)) and clamps every value to the documented range.
- It never writes to the keyboard firmware unless you ask. `avell-rgb save --confirm` (experimental, unverified) is the only command that sends the firmware save byte and persist frame. Do not script it.
- No firmware flashing code exists in this project.
- Without firmware save, the keyboard forgets its state at power off, and the daemon restores it.

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
avell-rgb effect wave --speed 5
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
