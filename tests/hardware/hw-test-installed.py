#!/usr/bin/env python3
"""Interactive hardware test of the INSTALLED avell-keyboard-rgb package.

Run as the normal user on the laptop (no sudo needed):

    python3 hw-test-installed.py [--dry-run] [--yes]

--dry-run prints every command and question and runs nothing. --yes skips only the
intro confirmation, never the observation questions. Every step drives the keyboard
through the `avell-rgb` CLI (and so the avell-rgbd daemon over D-Bus), asks what you
saw, and writes commands and answers to ~/Downloads/rgb-test-installed-YYYYMMDD-HHMMSS.log.
White is restored at the end. Needs only the Python 3.10+ standard library. The script
never sends firmware save frames and never uses --allow-unverified.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import glob
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TextIO

CLI = "avell-rgb"
TIMEOUT = 20
WHITE = "ffffff"
ZONES = ["ff0000", "00ff00", "0000ff", "ffffff"]
ZONE_NAMES = "red, green, blue, white (left to right)"
SEVEN = ["ff0000", "ff8800", "ffff00", "00ff00", "00ffff", "0000ff", "ff00ff"]
OTHER_SEVEN = ["ffffff", "ff00ff", "00ffff", "ffff00", "0000ff", "00ff00", "ff0000"]
DIRECTIONS = [0, 1, 2, 3, 4]
OTHER_EFFECTS = ["breathing", "flashing", "gradient"]


class Ctx:
    def __init__(self, dry_run: bool, assume_yes: bool, log: TextIO | None, log_path: Path | None):
        self.dry_run = dry_run
        self.assume_yes = assume_yes
        self.log = log
        self.log_path = log_path
        self.needs_root_hint = False

    def say(self, text: str = "") -> None:
        print(text)
        self.record(text)

    def record(self, text: str) -> None:
        if self.log:
            self.log.write(text + "\n")
            self.log.flush()


def real_home() -> tuple[Path, int, int]:
    name = os.environ.get("SUDO_USER") or ""
    try:
        entry = pwd.getpwnam(name) if name and os.geteuid() == 0 else pwd.getpwuid(os.getuid())
    except KeyError:
        entry = pwd.getpwuid(os.getuid())
    return Path(entry.pw_dir), entry.pw_uid, entry.pw_gid


def run(ctx: Ctx, argv: list[str], timeout: int = TIMEOUT) -> tuple[int, str]:
    shown = " ".join(argv)
    if ctx.dry_run:
        print(f"[dry-run] $ {shown}")
        return 0, ""
    ctx.record(f"$ {shown}")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError:
        out, code = f"command not found: {argv[0]}", 127
    except subprocess.TimeoutExpired:
        out, code = f"timeout after {timeout}s", 124
    else:
        out, code = (proc.stdout + proc.stderr).strip(), proc.returncode
    lowered = out.lower()
    if code != 0 and ("accessdenied" in lowered or "not authorized" in lowered):
        ctx.needs_root_hint = True
        out += "\n>>> The CLI was refused by polkit/D-Bus. Run from an active local session, or the CLI needs root here."
    ctx.record(f"  exit={code}")
    if out:
        for line in out.splitlines():
            ctx.record(f"  | {line}")
        print(f"  [{code}] {out.splitlines()[0]}")
    else:
        print(f"  [{code}]")
    return code, out


def cli(ctx: Ctx, *args: str) -> int:
    return run(ctx, [CLI, *args])[0]


def ask(ctx: Ctx, question: str) -> str:
    if ctx.dry_run:
        print(f"[dry-run] ask: {question}")
        return ""
    ctx.record(f"? {question}")
    try:
        answer = input(f"? {question}\n  > ").strip()
    except EOFError:
        answer = "(no input)"
    ctx.record(f"! {answer}")
    return answer


def pause(ctx: Ctx, message: str) -> None:
    if ctx.dry_run:
        print(f"[dry-run] wait: {message}")
        return
    ctx.record(f"~ {message}")
    with contextlib.suppress(EOFError):
        input(f"{message}\n  [Enter] ")


def step(ctx: Ctx, title: str) -> None:
    ctx.say("")
    ctx.say(f"=== {title} ===")


def journal(ctx: Ctx, since: str) -> None:
    code, out = run(
        ctx, ["journalctl", "-u", "avell-rgbd", "--since", since, "--no-pager", "-n", "40"]
    )
    if code != 0 or "No entries" in out:
        ctx.say("  (journal not readable or empty; add yourself to systemd-journal or ignore)")


def bcd_devices() -> list[str]:
    found = []
    for path in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        base = os.path.dirname(path)
        try:
            vid = Path(path).read_text().strip()
            pid = Path(base, "idProduct").read_text().strip()
            if (vid, pid) == ("048d", "ce00"):
                found.append(f"{base}: bcdDevice={Path(base, 'bcdDevice').read_text().strip()}")
        except OSError:
            continue
    return found


def preflight(ctx: Ctx) -> bool:
    step(ctx, "0. Preflight")
    if not ctx.dry_run and shutil.which(CLI) is None:
        ctx.say(f"FAIL: {CLI} not found in PATH. Is the package installed?")
        return False
    run(ctx, [CLI, "--version"])
    code, _ = run(ctx, [CLI, "status"])
    if not ctx.dry_run and code != 0:
        ctx.say("FAIL: daemon not reachable through the CLI.")
        if ctx.needs_root_hint:
            ctx.say("The CLI needs more privilege than this session has (polkit denied).")
        return False
    run(ctx, ["systemctl", "is-active", "avell-rgbd"])
    run(ctx, ["lsusb", "-d", "048d:ce00"])
    if ctx.dry_run:
        print("[dry-run] read /sys/bus/usb/devices/*/bcdDevice for 048d:ce00")
        print("[dry-run] read /proc/modules and look for ite_8291")
        return True
    devices = bcd_devices()
    ctx.say(
        "bcdDevice: " + ("; ".join(devices) if devices else "device 048d:ce00 not found in sysfs")
    )
    try:
        loaded = [
            ln for ln in Path("/proc/modules").read_text().splitlines() if ln.startswith("ite_8291")
        ]
    except OSError:
        loaded = []
    ctx.say("ite_8291 kernel module: " + ("LOADED (conflict!)" if loaded else "not loaded"))
    return True


def static_zones(ctx: Ctx, brightness: int = 30) -> None:
    cli(ctx, "effect", "static")
    cli(ctx, "set", *ZONES)
    cli(ctx, "brightness", str(brightness))


def suspend_round(ctx: Ctx, label: str) -> None:
    ask(
        ctx, f"[{label}] Is the keyboard showing the expected pattern right now? (y/n/what you see)"
    )
    since = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx.say("Now suspend the laptop (close the lid or use the menu), wake it and come back.")
    choice = ask(
        ctx, "Shall I run `systemctl suspend` for you? (y to run, anything else: do it yourself)"
    )
    if choice.lower() in ("y", "yes"):
        run(ctx, ["systemctl", "suspend"], timeout=60)
    pause(ctx, "After the laptop has resumed and you are back at this terminal, press Enter.")
    ask(
        ctx,
        f"[{label}] Did the same keyboard state come back by itself, without you doing anything? (y/n/what you see)",
    )
    ask(ctx, f"[{label}] About how many seconds after wake-up did the lighting return? (estimate)")
    run(ctx, [CLI, "status"])
    journal(ctx, since)


def step1(ctx: Ctx) -> None:
    step(ctx, "1. Suspend and resume")
    static_zones(ctx)
    ctx.say(f"Expected: {ZONE_NAMES} at brightness 30.")
    suspend_round(ctx, "static")
    cli(ctx, "effect", "wave", "--speed", "5")
    ctx.say("Expected: wave effect moving left to right.")
    suspend_round(ctx, "wave")


def step2(ctx: Ctx) -> None:
    step(ctx, "2. Wave directions (--direction 0 to 4)")
    cli(ctx, "brightness", "30")
    for d in DIRECTIONS:
        cli(ctx, "effect", "wave", "--speed", "4", "--direction", str(d))
        ask(
            ctx,
            f"wave --direction {d}: which way does it move (left to right, right to left, up, down, none, other)?",
        )


def step3(ctx: Ctx) -> None:
    step(ctx, "3. BEHAV (--direction) on other effects")
    for name in OTHER_EFFECTS:
        base = ["effect", name, "--speed", "4", "--palette", "ff0000", "00ff00", "0000ff"]
        cli(ctx, *base)
        ask(
            ctx,
            f"{name} with default direction: describe what you see (reference for the next values)",
        )
        for d in DIRECTIONS:
            cli(ctx, *base, "--direction", str(d))
            ask(
                ctx,
                f"{name} --direction {d}: what changed compared with the default? (nothing / describe)",
            )


def step4(ctx: Ctx) -> None:
    step(ctx, "4. Rainbow and the palette")
    cli(ctx, "effect", "rainbow", "--speed", "4", "--palette", *SEVEN)
    ctx.say("Palette sent: red, orange, yellow, green, cyan, blue, magenta.")
    ask(ctx, "rainbow, palette 1: how many distinct colours appear, and which?")
    cli(ctx, "effect", "rainbow", "--speed", "4", "--palette", *OTHER_SEVEN)
    ctx.say("Palette sent: white, magenta, cyan, yellow, blue, green, red.")
    ask(ctx, "rainbow, palette 2: did the colours change compared with palette 1? (y/n, describe)")
    cli(ctx, "effect", "rainbow", "--speed", "4")
    ask(ctx, "rainbow, default palette: same colours as before or different? (describe)")


def step5(ctx: Ctx) -> None:
    step(ctx, "5. Brightness only and colour cast")
    cli(ctx, "effect", "static")
    cli(ctx, "set", "ff0000", "00ff00", "0000ff", "ffffff")
    for level in (0, 10, 25, 50):
        cli(ctx, "brightness", str(level))
        ask(
            ctx,
            f"brightness {level}: do the hues shift (e.g. tint, colours turning yellowish) or only get dimmer? (describe)",
        )
    cli(ctx, "set", WHITE)
    cli(ctx, "brightness", "30")
    ask(
        ctx,
        "all zones white: is it pure white or tinted (blue, green, pink, yellow)? Zones differ?",
    )
    cli(ctx, "set", "ff8800", "ffff00", "00ffff", "ff00ff")
    ask(
        ctx,
        "orange, yellow, cyan, magenta: do these mixed colours look right, or is one clearly off? (describe)",
    )


def step6(ctx: Ctx) -> None:
    step(ctx, "6. Kernel log lines for 048d (for the re-enumeration question)")
    code, out = run(ctx, ["journalctl", "-k", "-b", "--no-pager"], timeout=40)
    if ctx.dry_run:
        print("[dry-run] filter the output for lines containing 048d (case-insensitive)")
        return
    lines = [ln for ln in out.splitlines() if "048d" in ln.lower()] if code == 0 else []
    ctx.say(f"{len(lines)} kernel lines mention 048d:")
    for ln in lines:
        ctx.say(f"  {ln}")
    if code != 0:
        ctx.say("  (kernel journal not readable as this user)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive hardware test of the installed package."
    )
    parser.add_argument("--dry-run", action="store_true", help="print commands, run nothing")
    parser.add_argument("--yes", action="store_true", help="skip the intro confirmation only")
    args = parser.parse_args()

    log = None
    log_path = None
    if not args.dry_run:
        home, uid, gid = real_home()
        downloads = home / "Downloads"
        created = not downloads.exists()
        downloads.mkdir(parents=True, exist_ok=True)
        log_path = downloads / f"rgb-test-installed-{dt.datetime.now():%Y%m%d-%H%M%S}.log"
        log = log_path.open("w", encoding="utf-8")
        if os.geteuid() == 0:
            if created:
                os.chown(downloads, uid, gid)
            os.chown(log_path, uid, gid)
    ctx = Ctx(args.dry_run, args.yes, log, log_path)
    ctx.say(
        f"avell-keyboard-rgb installed-product hardware test, {dt.datetime.now().isoformat(timespec='seconds')}"
    )
    if log_path:
        ctx.say(f"Log: {log_path}")
    if not args.yes and not args.dry_run:
        ans = input(
            "This changes the keyboard lighting and may suspend the laptop. Continue? [y/N] "
        )
        if ans.strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return 1
    try:
        if not preflight(ctx):
            return 2
        for fn in (step1, step2, step3, step4, step5, step6):
            fn(ctx)
        ask(ctx, "Any other remarks?")
    except KeyboardInterrupt:
        ctx.say("Interrupted.")
    finally:
        ctx.say("")
        ctx.say("Restoring white.")
        cli(ctx, "effect", "static")
        cli(ctx, "set", WHITE)
        cli(ctx, "brightness", "30")
        if log:
            log.close()
    if log_path:
        print(f"Done. Send back: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
