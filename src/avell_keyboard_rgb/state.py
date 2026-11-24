"""Keyboard state model, validation and on-disk store (state file and named profiles)."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import protocol

DEFAULT_STATE_DIR = Path("/var/lib/avell-keyboard-rgb")
PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$")
DEFAULT_ZONES = ["ffffff"] * protocol.ZONE_COUNT
DEFAULT_BRIGHTNESS = 25
DEFAULT_SPEED = 5


class InvalidArgument(ValueError):
    """A client sent a bad value."""


class ProfileNotFound(KeyError):
    """Unknown profile name."""


def check_range(label: str, value: int, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InvalidArgument(f"{label} must be an integer from {low} to {high}")
    return value


def norm_color(text: str) -> str:
    try:
        return protocol.format_color(protocol.parse_color(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidArgument(str(exc)) from exc


def norm_zone(zone: int) -> int:
    return check_range("zone", zone, 1, protocol.ZONE_COUNT)


def norm_profile_name(name: str) -> str:
    if not isinstance(name, str) or not PROFILE_NAME_RE.match(name):
        raise InvalidArgument(
            "profile name must match [A-Za-z0-9_.-]{1,64} and not start with a dot"
        )
    return name


def norm_effect(name: str, options: dict[str, Any]) -> dict[str, Any]:
    """Validate a firmware effect request. Name 'static' is handled by the caller."""
    if name not in protocol.MODES:
        raise InvalidArgument(f"unknown firmware effect {name!r}")
    known = {"speed", "palette", "direction", "allow_unverified"}
    extra = set(options) - known
    if extra:
        raise InvalidArgument(f"unknown option(s): {', '.join(sorted(extra))}")
    allow = options.get("allow_unverified", False)
    if not isinstance(allow, bool):
        raise InvalidArgument("allow_unverified must be a boolean")
    if name in protocol.UNSUPPORTED_EFFECTS and not allow:
        raise InvalidArgument(
            f"effect {name!r} is unsupported on ITE 8291 rev 0.02 (it did nothing in the "
            "hardware test); pass allow_unverified=true to send it anyway"
        )
    speed = check_range(
        "speed", options.get("speed", DEFAULT_SPEED), protocol.SPEED_MIN, protocol.SPEED_MAX
    )
    direction = check_range(
        "direction",
        options.get("direction", protocol.default_direction(name)),
        protocol.DIRECTION_MIN,
        protocol.DIRECTION_MAX,
    )
    palette_in = options.get("palette", [])
    if not isinstance(palette_in, (list, tuple)) or len(palette_in) > protocol.PALETTE_SIZE:
        raise InvalidArgument(f"palette must hold at most {protocol.PALETTE_SIZE} colours")
    palette = [norm_color(c) for c in palette_in]
    result: dict[str, Any] = {
        "name": name,
        "speed": speed,
        "palette": palette,
        "direction": direction,
    }
    if allow:
        result["allow_unverified"] = True
    return result


@dataclass
class State:
    power: bool = True
    brightness: int = DEFAULT_BRIGHTNESS
    zones: list[str] = field(default_factory=lambda: list(DEFAULT_ZONES))
    effect: dict[str, Any] | None = None
    software: dict[str, Any] | None = None

    @property
    def mode(self) -> str:
        if not self.power:
            return "off"
        return self.effect["name"] if self.effect else "static"

    def to_dict(self) -> dict[str, Any]:
        return {
            "power": self.power,
            "brightness": self.brightness,
            "zones": list(self.zones),
            "effect": self.effect,
            "software": self.software,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> State:
        """Rebuild from stored JSON, validating every field. Raises InvalidArgument."""
        if not isinstance(data, dict):
            raise InvalidArgument("state must be an object")
        zones_in = data.get("zones", DEFAULT_ZONES)
        if not isinstance(zones_in, list) or len(zones_in) != protocol.ZONE_COUNT:
            raise InvalidArgument("zones must be a list of 4 colours")
        effect = data.get("effect")
        if effect is not None:
            if not isinstance(effect, dict):
                raise InvalidArgument("effect must be an object or null")
            effect = norm_effect(
                str(effect.get("name", "")),
                {k: v for k, v in effect.items() if k != "name"},
            )
        software = data.get("software")
        if software is not None:
            if not isinstance(software, dict) or not isinstance(software.get("name"), str):
                raise InvalidArgument("software must be an object with a name, or null")
            opts = software.get("options", {})
            if not isinstance(opts, dict):
                raise InvalidArgument("software options must be an object")
            software = {"name": software["name"], "options": opts}
        power = data.get("power", True)
        if not isinstance(power, bool):
            raise InvalidArgument("power must be a boolean")
        return cls(
            power=power,
            brightness=check_range(
                "brightness",
                data.get("brightness", DEFAULT_BRIGHTNESS),
                protocol.BRIGHTNESS_MIN,
                protocol.BRIGHTNESS_MAX,
            ),
            zones=[norm_color(c) for c in zones_in],
            effect=effect,
            software=software,
        )


class StateStore:
    """JSON files under a directory: state.json and profiles/<name>.json."""

    def __init__(self, directory: Path = DEFAULT_STATE_DIR) -> None:
        self.directory = Path(directory)
        self.profiles_dir = self.directory / "profiles"

    @property
    def state_file(self) -> Path:
        return self.directory / "state.json"

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _read(self, path: Path) -> State:
        with open(path) as handle:
            return State.from_dict(json.load(handle))

    def load(self) -> State:
        """Stored state, or defaults when missing or corrupt (a bad file is kept as .bad)."""
        try:
            return self._read(self.state_file)
        except FileNotFoundError:
            return State()
        except (OSError, ValueError):
            with contextlib.suppress(OSError):
                os.replace(self.state_file, self.state_file.with_suffix(".bad"))
            return State()

    def save(self, state: State) -> None:
        self._write(self.state_file, state.to_dict())

    def _profile_path(self, name: str) -> Path:
        return self.profiles_dir / f"{norm_profile_name(name)}.json"

    def save_profile(self, name: str, state: State) -> None:
        self._write(self._profile_path(name), state.to_dict())

    def load_profile(self, name: str) -> State:
        path = self._profile_path(name)
        try:
            return self._read(path)
        except FileNotFoundError as exc:
            raise ProfileNotFound(name) from exc
        except (OSError, ValueError) as exc:
            raise InvalidArgument(f"profile {name!r} is unreadable: {exc}") from exc

    def delete_profile(self, name: str) -> None:
        try:
            self._profile_path(name).unlink()
        except FileNotFoundError as exc:
            raise ProfileNotFound(name) from exc

    def list_profiles(self) -> list[str]:
        if not self.profiles_dir.is_dir():
            return []
        return sorted(
            p.stem for p in self.profiles_dir.glob("*.json") if PROFILE_NAME_RE.match(p.stem)
        )
