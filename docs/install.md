# Install

Check [hardware.md](hardware.md) first: only the ITE 8291 `048d:ce00` with bcdDevice 0.02 is supported.

## Packages

Packages for Debian family and Fedora family systems are attached to each [release](https://github.com/andremmfaria/avell-keyboard-rgb/releases). They are architecture independent.

```text
sudo apt install ./avell-keyboard-rgb_<version>_all.deb
sudo dnf install ./avell-keyboard-rgb-<version>-1.noarch.rpm
```

The packages are built from `nfpm.yaml` by CI; see [development.md](development.md) for how and when.

## Requirements

Runtime dependencies are declared in the packages, so the package manager installs them.

| | Debian, Ubuntu (24.04 or newer) | Fedora |
|---|---|---|
| Python 3.10 or newer | `python3` | `python3` |
| PyGObject | `python3-gi` | `python3-gobject` |
| GTK 4 | `gir1.2-gtk-4.0` | `gtk4` |
| libadwaita 1.5 or newer | `gir1.2-adw-1` | `libadwaita` |
| D-Bus | `dbus` | `dbus-daemon` |
| polkit | `polkitd` (older: `policykit-1`) | `polkit` |
| systemd and udev | `systemd`, `udev` | `systemd` |

The Debian package lists `udev` as a dependency; the Fedora package declares `systemd` only.

## What the package installs

| Path | Purpose |
|---|---|
| `/usr/lib/avell-keyboard-rgb/avell_keyboard_rgb` | The Python code |
| `/usr/bin/avell-rgb`, `/usr/bin/avell-rgbd`, `/usr/bin/avell-rgb-gui` | Launchers for the CLI, the daemon and the GUI |
| `/usr/lib/systemd/system/avell-rgbd.service` | The daemon unit, with sandboxing |
| `/usr/lib/udev/rules.d/99-avell-keyboard-rgb.rules` | Gives the `avell-rgb` group access to the keyboard's hidraw node (mode 0660) and starts the daemon when the keyboard appears |
| `/usr/lib/sysusers.d/avell-keyboard-rgb.conf` | Creates the system user and group `avell-rgb` |
| `/usr/share/dbus-1/system.d/io.github.andremmfaria.AvellRgb.conf` | D-Bus policy |
| `/usr/share/dbus-1/system-services/io.github.andremmfaria.AvellRgb.service` | D-Bus activation |
| `/usr/share/polkit-1/actions/io.github.andremmfaria.AvellRgb.policy` | The polkit action that authorises changes |
| `/usr/share/applications/` and `/usr/share/icons/hicolor/` | Desktop entry and icons for the GUI |
| `/usr/share/doc/avell-keyboard-rgb/` | This documentation (`README.md`, `todo.md` and `docs/`) and the licence as `copyright` |

The code lives in a private directory because the distributions disagree about where architecture independent Python code goes (`dist-packages` on Debian, a Python version specific `site-packages` on Fedora). A private directory keeps one package working across Python releases up to 3.14. The launchers put that directory on `PYTHONPATH` and run `/usr/bin/python3`. It also means pip is never involved, so PEP 668 "externally managed environment" does not apply.

After installing or upgrading, the maintainer script creates the user (`systemd-sysusers`), reloads udev rules and re-triggers hidraw devices, reloads systemd and D-Bus, restarts a running daemon, and refreshes the icon and desktop caches. The daemon starts when the keyboard appears (udev) or when a client calls it (D-Bus activation); the unit is not enabled at boot. What each piece allows is explained in [safety.md](safety.md).

## From source

Running from a checkout is meant for development and does not need root: start the daemon on a private session bus without polkit, then point the CLI at it. The steps are in [development.md](development.md).

A system wide install from source is not documented or tested. The files the package installs and their destinations are listed in `nfpm.yaml`; the udev rule header notes that from source it is copied to `/etc/udev/rules.d/`. The user `avell-rgb`, the D-Bus policy and the polkit action (including its owner annotation, see [troubleshooting.md](troubleshooting.md)) must all be in place for the daemon to work as a system service.

## Uninstalling

Remove the package with `sudo apt remove avell-keyboard-rgb` or `sudo dnf remove avell-keyboard-rgb`. The pre-removal script stops the daemon and the post-removal script reloads udev and systemd.

Removal keeps the saved state and profiles in `/var/lib/avell-keyboard-rgb` and keeps the `avell-rgb` user. These are not deleted on purge either, because the maintainer scripts never delete them. To remove them by hand, delete that directory and run `sudo userdel avell-rgb`.

## Related documentation

- [usage.md](usage.md): what to run after installing.
- [hardware.md](hardware.md): check your keyboard is supported before installing.
- [safety.md](safety.md): the permissions model the package sets up.
- [troubleshooting.md](troubleshooting.md): problems after installing.
- [development.md](development.md): packaging, CI and running from source.
