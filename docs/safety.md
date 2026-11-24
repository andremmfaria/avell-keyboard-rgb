# Safety

This page describes what the daemon sends to the keyboard and what permissions the installation uses. The frame formats are in [protocol.md](protocol.md).

## What the daemon sends

- Only the documented frames: colour definitions (`14 ...`), the mode frame and the off frame (both `08 ...`). No other opcode exists in the code. Each frame is 8 bytes and the transport refuses to send anything else.
- Every value is limited to its documented range before it reaches the wire: brightness 0 to 50, user speed 0 to 10, direction 0 to 4, colour channels 0 to 255, palette slots 1 to 7, zones 1 to 4. The clamping is in `protocol.py`. On the D-Bus interface, out of range values are rejected with `InvalidArgument` instead of being clamped, and the CLI clamps and prints a message before sending (see [dbus-interface.md](dbus-interface.md) and [usage.md](usage.md)).
- The wire speed byte is never 0, because wire speed 0 made effects glitch and stop on the real keyboard (see [hardware.md](hardware.md)).
- Software effects are paced: at most their `fps` (1 to 20, default 10) writes a second, and an unchanged frame is not sent again.
- Writes are serialised, so frames from different clients never interleave.

## No firmware writes, no flashing

- The daemon never writes to the keyboard firmware. The mode frame's save byte is always 0, and the persist frame that an earlier experiment used, along with its `save` command, was removed from the code.
- Persistence across power cycles is done by the daemon: it stores its own state in `/var/lib/avell-keyboard-rgb/state.json` and re-applies it at start, after resume from suspend, and when the keyboard comes back. The keyboard forgets its state at power off.
- No firmware update or flashing code exists in this project.
- `raindrop` is rejected unless the caller passes `--allow-unverified`, because it did nothing on rev 0.02.

## Permissions model

| Piece | What it does |
|---|---|
| System user `avell-rgb` | The daemon runs as this unprivileged user, created by sysusers.d. It has no login |
| udev rule | Gives the group `avell-rgb` access to the keyboard's hidraw node with mode 0660. It is never world-writable. The daemon picks the vendor interface by its usage page |
| systemd unit | Runs as `avell-rgb` with sandboxing: no new privileges, no capabilities, `ProtectSystem=strict`, `ProtectHome`, no network, only hidraw character devices reachable, and a system call filter. Its state directory is `/var/lib/avell-keyboard-rgb` |
| D-Bus policy | Controls who may own the service name and call it on the system bus |
| polkit action `io.github.andremmfaria.AvellRgb.control` | Needed for every method that changes the keyboard or the stored state. Allowed without a prompt for a local session that is active, denied otherwise |

Reading the state needs no authorisation, so anyone on the machine can run `avell-rgb status`. Profiles and state files are readable by anyone because the state directory mode is 0755 and the files are written with mode 0644; they contain colours and effect settings only.

The daemon is not root, so polkit only lets it check callers of other users if the action names the daemon user as owner, using the `org.freedesktop.policykit.owner` annotation. `deploy/check-deploy.sh` and `tests/test_deploy_policy.py` enforce that the annotation, the unit's `User=` and the sysusers name match. If you see "not authorized" on every change, see [troubleshooting.md](troubleshooting.md).

## Related documentation

- [protocol.md](protocol.md): the frames and what is verified.
- [hardware.md](hardware.md): evidence from the real keyboard.
- [dbus-interface.md](dbus-interface.md): authorisation and errors on the bus.
- [install.md](install.md): what the package sets up.
- [troubleshooting.md](troubleshooting.md): permission problems.
- [development.md](development.md): the checks that guard the deploy files.
