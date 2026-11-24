# Troubleshooting

Start with `avell-rgb status` and `journalctl -u avell-rgbd`. The daemon log is the main source of information. Status works without authorisation, so it also shows whether the daemon and the keyboard are reachable at all.

## Every change says "not authorized"

If every command that changes the keyboard says "not authorized" while `avell-rgb status` works, check the daemon log with `journalctl -u avell-rgbd` for polkit errors.

The message "Only trusted callers (e.g. uid 0 or an action owner) can use CheckAuthorization() for subjects belonging to other identities" means the installed polkit policy lacks the `org.freedesktop.policykit.owner` annotation naming the daemon user `avell-rgb`. Version 0.1.1 and newer ship it; upgrade the package. The annotation is in `/usr/share/polkit-1/actions/io.github.andremmfaria.AvellRgb.policy`. Why it is needed is explained in [safety.md](safety.md).

Without that error, the caller is probably not in an active local session, which the polkit action denies by default (it allows only an active local session).

## The daemon is not running

The daemon starts when the keyboard appears (udev) or when a client calls it (D-Bus activation); it is not enabled at boot. Check it with `systemctl status avell-rgbd`. The GUI shows a banner "The avell-rgbd daemon is not running" when it cannot reach the daemon. The CLI prints a D-Bus error. The post-install script of the package reloads D-Bus and udev and re-triggers hidraw devices; see [install.md](install.md).

## The keyboard is not found

`avell-rgb status` shows `NOT connected` on its keyboard line, and the `last error` line explains why when there is one. The daemon looks for a hidraw node whose uevent has `HID_ID=0003:0000048D:0000CE00` and whose report descriptor has the vendor usage page `0xFF12`. While the keyboard is missing or a write failed, your requests are stored and the daemon retries every 5 seconds, so the state is applied when the keyboard returns. Clients get `DeviceUnavailable` for requests made meanwhile.

Things to check:

- That the keyboard is a supported one: `lsusb -v -d 048d:ce00 | grep bcdDevice` must show 0.02 (see [hardware.md](hardware.md)).
- That the `tuxedo-drivers` `ite_8291` module is not loaded for the same device (see [hardware.md](hardware.md)).
- That the udev rule is installed and the hidraw node belongs to the group `avell-rgb` with mode 0660: `ls -l /dev/hidraw*`. The package re-triggers udev when installed; replug or reboot if the node was created before.
- The daemon log, which names the hidraw path it could not open.

## After suspend

The daemon re-applies the stored state after resume (logind `PrepareForSleep`), and retries while a write fails. This path has not been tested on real hardware yet (see [hardware.md](hardware.md)). If the keyboard stays dark after resume, run `avell-rgb on`, and include `journalctl -k | grep 048d` and `journalctl -u avell-rgbd` when reporting it, because a USB re-enumeration is decided from that evidence (see [todo.md](../todo.md)).

## Speed 9 and 10 look the same

This is expected. Wire speed 0 is invalid on the keyboard (effects glitch and stop), so user speeds 9 and 10 both send the fastest valid wire value. See [usage.md](usage.md) and [protocol.md](protocol.md).

## An effect shows fewer colours than expected

Rainbow showed only red, orange, yellow and green on four regions in the hardware test, and raindrop does nothing on rev 0.02. Both are known; see [hardware.md](hardware.md).

## Reporting a problem

Include the output of `avell-rgb status`, `avell-rgb --version`, the `bcdDevice` value, and the relevant lines of `journalctl -u avell-rgbd`. To test the installed package step by step, see the hardware test in [development.md](development.md).

## Related documentation

- [install.md](install.md): what the package installs and how the daemon starts.
- [safety.md](safety.md): the permissions model behind "not authorized".
- [hardware.md](hardware.md): supported revision and known limits.
- [usage.md](usage.md): speed semantics and commands.
- [development.md](development.md): running the daemon from a checkout and the hardware test.
