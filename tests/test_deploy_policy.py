"""The polkit policy must name the daemon user as action owner (see the policy comment)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"
OWNER_KEY = "org.freedesktop.policykit.owner"
ACTION_ID = "io.github.andremmfaria.AvellRgb.control"


def policy_owner() -> str | None:
    root = ET.parse(DEPLOY / "io.github.andremmfaria.AvellRgb.policy").getroot()
    for action in root.findall("action"):
        if action.get("id") != ACTION_ID:
            continue
        for note in action.findall("annotate"):
            if note.get("key") == OWNER_KEY:
                return (note.text or "").strip()
    return None


def unit_user() -> str:
    match = re.search(r"^User=(\S+)$", (DEPLOY / "avell-rgbd.service").read_text(), re.M)
    assert match is not None
    return match.group(1)


def sysusers_name() -> str:
    for line in (DEPLOY / "avell-keyboard-rgb.sysusers").read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "u":
            return fields[1]
    raise AssertionError("no user line in the sysusers file")


def test_policy_has_owner_annotation() -> None:
    owner = policy_owner()
    assert owner is not None, "policy action lacks the polkit owner annotation"
    assert owner.startswith("unix-user:")


def test_owner_matches_unit_user_and_sysusers() -> None:
    assert policy_owner() == f"unix-user:{unit_user()}"
    assert unit_user() == sysusers_name()
