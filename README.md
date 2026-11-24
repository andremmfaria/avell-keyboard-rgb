<p align="center"><img src="deploy/io.github.andremmfaria.AvellRgbGui.svg" alt="avell-keyboard-rgb logo: four glowing backlight zones" width="128" height="128"></p>

<h1 align="center">avell-keyboard-rgb</h1>

A daemon, command line tool and GTK4 GUI for the 4 zone keyboard backlight of the ITE 8291 controller (USB `048d:ce00`, bcdDevice 0.02) found in some Avell and Clevo/Tongfang laptops. The daemon owns the keyboard and exposes a small D-Bus interface; the CLI and the GUI are clients of it.

This is an independent, unofficial project, not affiliated with or endorsed by Avell, ITE or Clevo. Product names are used only to identify the hardware this software works with.

Status: version 0.1.2, verified on real hardware (one ITE 8291 rev 0.02 laptop keyboard, 2026-11-24). Some items are not tested yet; see [docs/hardware.md](docs/hardware.md).

## Features

- Four independent zone colours, brightness 0 to 50, on and off.
- Firmware effects: breathing, wave, rainbow, flashing, gradient, with speed, direction and a palette of up to 7 colours.
- Software effects run by the daemon: `cpu-temp`, `battery` and `fade`.
- Named profiles, and a "flash this zone" button to see which zone is which.
- The daemon re-applies the stored state at start and after resume from suspend, and retries while the keyboard is missing.
- Never writes to the keyboard firmware.

## Quick start

```text
sudo apt install ./avell-keyboard-rgb_<version>_all.deb    # from the Releases page
avell-rgb set ff0000 00ff00 0000ff ffffff                  # four zones, left to right
avell-rgb-gui
```

Packages are attached to each [release](https://github.com/andremmfaria/avell-keyboard-rgb/releases). Fedora family systems use the `.rpm` with `sudo dnf install`.

## Documentation

- [docs/README.md](docs/README.md): documentation index and reading order.
- [docs/install.md](docs/install.md): packages, installing from source, requirements, uninstalling.
- [docs/usage.md](docs/usage.md): CLI reference, GUI, effects, profiles, speed and zones.
- [docs/hardware.md](docs/hardware.md): supported hardware, limits, and the hardware test results.
- [docs/safety.md](docs/safety.md): what the daemon sends, value clamping, permissions model.
- [docs/troubleshooting.md](docs/troubleshooting.md): common problems and what to check.
- [docs/development.md](docs/development.md): repository layout, tests, packaging, CI and releases.
- [docs/protocol.md](docs/protocol.md): the USB protocol, with verified and unverified assumptions.
- [docs/dbus-interface.md](docs/dbus-interface.md): the D-Bus contract between daemon and clients.
- [todo.md](todo.md): open items and roadmap.
- [LICENSE](LICENSE): MIT.
