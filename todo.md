# TODO

Open items after the first hardware test on 2026-11-24 (see [docs/protocol.md](docs/protocol.md) for the verified and unverified protocol assumptions and [docs/hardware.md](docs/hardware.md) for the results). Development notes are in [docs/development.md](docs/development.md).

## Pending decision

- [ ] Add a udev rule line that signals the daemon (SIGHUP via systemd) when the keyboard device is added, so the daemon reopens the hidraw node and reapplies the saved state right after a re-enumeration that is not a suspend. Today it only recovers after a failed write and a 5 second retry. The alternative is a pyudev listener inside the daemon, which adds a dependency on both distros.

## Verification on hardware

- [ ] Wave directions other than BEHAV 1 (left to right), and the BEHAV byte on the other effects.
- [ ] Rainbow showed only red, orange, yellow and green on four regions, so find out whether it uses the palette slots and how.
- [ ] State across suspend and resume (logind PrepareForSleep reapply path).
- [ ] Confirm the slow end of the speed range (user 0, wire 10) and that user 9 and 10 look identical, using the speed sweep step of [tests/hardware/hw-test-installed.py](tests/hardware/README.md).
- [ ] Brightness-only frame and colour cast of the zone colours.
- [ ] Look at the GUI on screen (so far only smoke tests under Xvfb).

## Packaging and CI

- [ ] Confirm the first GitHub Actions runs (CI, Package, Tag Release) are green, and fix anything that fails.
- [ ] Install the built .deb on branco and check the daemon, polkit path, udev rule, sysusers and maintainer scripts on a real system. Partly done: installed on branco, the polkit owner annotation bug was found and fixed in 0.1.1; icon and maintainer-script checks still to confirm.
- [ ] Run the rpm checks (skipped locally because rpm is not installed; CI runs them) and test an install on a Fedora-family system.
- [x] Test the code on Python 3.10 to 3.14 and in a venv without PyGObject (CI job `portable` runs the suite on 3.10 to 3.14 without PyGObject, and `tests/test_imports.py` pins which modules import without `gi`).

## Possible later work

- [ ] Raindrop mode does nothing on rev 0.02, so it is rejected unless `--allow-unverified` is passed. Revisit only if another firmware revision turns up.
- [ ] Identify the Windows driver with the Chinese-lettered name (Avell or Clevo control software) from Device Manager details, to see whether it exposes anything beyond the 4 zones.
