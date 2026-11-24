# Hardware tests

This directory holds interactive scripts that are run by hand on a laptop with the real ITE 8291 keyboard and are never run by CI or collected by pytest, because their file names do not start with test_ and contain a hyphen.

`hw-test-installed.py` tests the installed package (the avell-rgbd daemon and the avell-rgb CLI) rather than raw frames. It checks the daemon and device, then walks through suspend and resume, wave directions, the direction byte on other effects, the rainbow palette question, brightness and colour cast, a speed sweep of the wave effect and the kernel log lines that mention 048d, asking what you see at each step and writing commands and answers to `~/Downloads/rgb-test-installed-YYYYMMDD-HHMMSS.log`.

Run it as the normal user with `python3 hw-test-installed.py`. Add `--dry-run` to only print the commands and questions, and `--yes` to skip the introductory confirmation (the observation questions are always asked). It needs only the Python standard library, never saves anything to the keyboard firmware, never uses `--allow-unverified`, and restores white lighting when it finishes. The suspend step offers to run `systemctl suspend` for you.

Results so far are in [../../docs/hardware.md](../../docs/hardware.md), and the setup for running tests and checks is in [../../docs/development.md](../../docs/development.md).

## Related documentation

- [Development guide](../../docs/development.md): dev setup, tests and checks.
- [Hardware](../../docs/hardware.md): supported hardware and test results.
- [Protocol](../../docs/protocol.md): which assumptions are still unverified.
- [Safety](../../docs/safety.md): what the software never sends.
