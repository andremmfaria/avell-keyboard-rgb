# TODO

Open items after the first hardware test on 2026-11-24 (see docs/protocol.md for the verified and unverified protocol assumptions).

## Pending decision

- [ ] Add a udev rule line that signals the daemon (SIGHUP via systemd) when the keyboard device is added, so the daemon reopens the hidraw node and reapplies the saved state right after a re-enumeration that is not a suspend. Today it only recovers after a failed write and a 5 second retry. The alternative is a pyudev listener inside the daemon, which adds a dependency on both distros.

## Verification on hardware

- [ ] Wave directions other than BEHAV 1 (left to right), and the BEHAV byte on the other effects.
- [ ] Rainbow showed only red, orange, yellow and green on four regions, so find out whether it uses the palette slots and how.
- [ ] State across suspend and resume (logind PrepareForSleep reapply path).
- [ ] Brightness-only frame and colour cast of the zone colours.
- [ ] Look at the GUI on screen (so far only smoke tests under Xvfb).

## Packaging and CI

- [ ] Confirm the first GitHub Actions runs (CI, Package, Tag Release) are green, and fix anything that fails.
- [ ] Install the built .deb on branco and check the daemon, polkit path, udev rule, sysusers and maintainer scripts on a real system.
- [ ] Run the rpm checks (skipped locally because rpm is not installed; CI runs them) and test an install on a Fedora-family system.
- [ ] Test the code on Python 3.10 to 3.13 and in a venv without PyGObject (not run so far).

## Possible later work

- [ ] Raindrop mode does nothing on rev 0.02, so it is rejected unless `--allow-unverified` is passed. Revisit only if another firmware revision turns up.
- [ ] Identify the Windows driver with the Chinese-lettered name (Avell or Clevo control software) from Device Manager details, to see whether it exposes anything beyond the 4 zones.
