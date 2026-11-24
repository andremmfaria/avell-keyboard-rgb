# Documentation

This directory holds the documentation of avell-keyboard-rgb, a daemon, command line tool and GTK4 GUI for the 4 zone ITE 8291 keyboard backlight. The project overview is in the [root README](../README.md); the roadmap is in [todo.md](../todo.md).

## Reading order

If you only want to use it, read these in order:

1. [install.md](install.md): install the package or run from source, and what the package sets up on the system.
2. [usage.md](usage.md): the `avell-rgb` commands, the GUI, effects, profiles and how speed works.
3. [troubleshooting.md](troubleshooting.md): what to check when something does not work.

Before you trust it on your laptop, read these:

1. [hardware.md](hardware.md): which keyboards are supported, the known limits and what has been tested on real hardware.
2. [safety.md](safety.md): what the daemon sends to the keyboard and which permissions it needs.

If you want to change the code or write another client, read these:

1. [development.md](development.md): repository layout, dev setup, tests, packaging, CI and releases.
2. [protocol.md](protocol.md): the wire protocol and the evidence behind each assumption.
3. [dbus-interface.md](dbus-interface.md): the D-Bus API that every client uses.

Hardware test scripts have their own short guide in [../tests/hardware/README.md](../tests/hardware/README.md).

## Index

| File | Contents |
|---|---|
| [install.md](install.md) | Packages, from source, requirements, uninstalling, what the package installs |
| [usage.md](usage.md) | CLI reference, GUI, firmware and software effects, profiles, speed, zones, brightness |
| [hardware.md](hardware.md) | Supported hardware, how to check bcdDevice, unsupported devices, test results |
| [safety.md](safety.md) | Frames sent, clamping, no firmware writes, permissions model |
| [troubleshooting.md](troubleshooting.md) | Not authorized, daemon not running, keyboard missing, suspend, speed 10 |
| [development.md](development.md) | Layout, dev setup, tests, hardware test, packaging, CI, release flow |
| [protocol.md](protocol.md) | Device, transport, frames, hardware test evidence |
| [dbus-interface.md](dbus-interface.md) | Bus names, interface XML, methods, errors, daemon guarantees |

## Related documentation

- [Project README](../README.md)
- [install.md](install.md)
- [usage.md](usage.md)
- [hardware.md](hardware.md)
- [safety.md](safety.md)
- [troubleshooting.md](troubleshooting.md)
- [development.md](development.md)
- [protocol.md](protocol.md)
- [dbus-interface.md](dbus-interface.md)
