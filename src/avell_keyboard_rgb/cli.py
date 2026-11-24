"""avell-rgb: command line client for the avell-rgbd daemon."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__, protocol

EPILOG = """\
examples:
  avell-rgb set ff0000 00ff00 0000ff ffffff   four zone colours, left to right
  avell-rgb set 3366ff                        all zones the same colour
  avell-rgb zone 2 ff8800                     change one zone
  avell-rgb brightness 30                     0 to 50
  avell-rgb effect wave --speed 8             firmware effect, speed 0 to 10, higher is faster
  avell-rgb effect breathing --palette ff0000 0000ff
  avell-rgb effect static                     back to plain colours
  avell-rgb off | on
  avell-rgb profile save work | load work | list | delete work
  avell-rgb software-effect start cpu-temp -o min_temp=45 -o max_temp=85
  avell-rgb software-effect start fade -o period=60 -o colors=ff0000,0000ff
  avell-rgb software-effect stop
  avell-rgb identify 3                        flash zone 3
  avell-rgb status
"""


def _range_int(low: int, high: int, label: str) -> Any:
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{label} must be a whole number") from None
        if not low <= value <= high:
            print(f"avell-rgb: {label} {value} clamped to {low}..{high}", file=sys.stderr)
        return max(low, min(high, value))

    return parse


def _color(text: str) -> str:
    try:
        return protocol.format_color(protocol.parse_color(text))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _zone(text: str) -> int:
    try:
        zone = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("zone must be 1 to 4") from None
    if not 1 <= zone <= protocol.ZONE_COUNT:
        raise argparse.ArgumentTypeError("zone must be 1 to 4")
    return zone


def _option(text: str) -> tuple[str, Any]:
    if "=" not in text:
        raise argparse.ArgumentTypeError("expected key=value")
    key, value = text.split("=", 1)
    if "," in value:
        return key, [v for v in value.split(",") if v]
    try:
        return key, int(value)
    except ValueError:
        return key, value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avell-rgb",
        description="Control the 4 zone keyboard backlight through the avell-rgbd daemon.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--bus",
        choices=("system", "session"),
        default="system",
        help="D-Bus to use (default: system)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    sub.add_parser("status", help="show daemon and keyboard state")

    p = sub.add_parser("set", help="set zone colours (4 colours, or 1 for all zones)")
    p.add_argument("colors", nargs="+", type=_color, metavar="RRGGBB")

    p = sub.add_parser("zone", help="set one zone")
    p.add_argument("zone", type=_zone)
    p.add_argument("color", type=_color, metavar="RRGGBB")

    p = sub.add_parser("brightness", help="set brightness 0 to 50")
    p.add_argument(
        "value", type=_range_int(protocol.BRIGHTNESS_MIN, protocol.BRIGHTNESS_MAX, "brightness")
    )

    sub.add_parser("on", help="turn the backlight on (re-apply stored state)")
    sub.add_parser("off", help="turn the backlight off")

    p = sub.add_parser("effect", help="firmware effect, or 'static' for plain colours")
    # raindrop is accepted here so the daemon can explain why it is refused; it is
    # not listed in the help and only goes through with --allow-unverified.
    p.add_argument(
        "name",
        choices=("static", *protocol.FIRMWARE_EFFECTS, *protocol.UNSUPPORTED_EFFECTS),
        metavar="{" + ",".join(("static", *protocol.FIRMWARE_EFFECTS)) + "}",
    )
    p.add_argument(
        "--speed",
        type=_range_int(protocol.SPEED_MIN, protocol.SPEED_MAX, "speed"),
        help="0 to 10, higher is faster (default 5)",
    )
    p.add_argument("--palette", nargs="+", type=_color, metavar="RRGGBB", help="up to 7 colours")
    p.add_argument(
        "--direction",
        type=_range_int(protocol.DIRECTION_MIN, protocol.DIRECTION_MAX, "direction"),
        help="0 to 4; only wave with 1 (left to right, the wave default) is verified",
    )
    p.add_argument(
        "--allow-unverified",
        action="store_true",
        help="allow an effect that does nothing on rev 0.02 (raindrop)",
    )

    p = sub.add_parser("identify", help="flash one zone to tell which is which")
    p.add_argument("zone", type=_zone)

    p = sub.add_parser("profile", help="named profiles")
    psub = p.add_subparsers(dest="action", required=True, metavar="ACTION")
    for action in ("save", "load", "delete"):
        pp = psub.add_parser(action, help=f"{action} a profile")
        pp.add_argument("name")
    psub.add_parser("list", help="list profiles")

    p = sub.add_parser(
        "software-effect", help="effects driven by the daemon (cpu-temp, battery, fade)"
    )
    ssub = p.add_subparsers(dest="action", required=True, metavar="ACTION")
    pp = ssub.add_parser("start", help="start an effect")
    pp.add_argument("name")
    pp.add_argument(
        "--fps", type=_range_int(1, 20, "fps"), help="updates per second, 1 to 20 (default 10)"
    )
    pp.add_argument(
        "-o",
        "--option",
        action="append",
        default=[],
        type=_option,
        metavar="KEY=VALUE",
        help="effect option, repeatable; lists use commas",
    )
    ssub.add_parser("stop", help="stop the running effect")
    ssub.add_parser("list", help="list effect names")

    p = sub.add_parser(
        "save",
        help="EXPERIMENTAL: store the current state in keyboard firmware",
        description="Writes the current state into the keyboard firmware (SAVE byte and persist "
        "frame). Experimental and unverified on hardware. Needs --confirm.",
    )
    p.add_argument("--confirm", action="store_true", help="acknowledge the experimental write")
    return parser


def _format_status(state: dict[str, Any]) -> str:
    lines = [
        f"daemon version : {state.get('version', '?')}",
        f"keyboard       : {'connected' if state.get('device_connected') else 'NOT connected'}"
        + (f" ({state['device_path']})" if state.get("device_path") else ""),
        f"power          : {'on' if state.get('power') else 'off'}",
        f"mode           : {state.get('mode')}",
        f"brightness     : {state.get('brightness')} / {protocol.BRIGHTNESS_MAX}",
        f"zones          : {' '.join(state.get('zones', []))}",
    ]
    if state.get("effect"):
        e = state["effect"]
        lines.append(
            f"effect         : {e.get('name')} speed={e.get('speed')} "
            f"direction={e.get('direction')}"
        )
    if state.get("software_effect"):
        lines.append(
            f"software effect: {state['software_effect']} {state.get('software_options', {})}"
        )
    if state.get("last_error"):
        lines.append(f"last error     : {state['last_error']}")
    return "\n".join(lines)


def run(args: argparse.Namespace, client: Any) -> int:
    cmd = args.command
    if cmd == "status":
        print(_format_status(client.get_state()))
    elif cmd == "set":
        colors = args.colors
        if len(colors) == 1:
            colors = colors * protocol.ZONE_COUNT
        if len(colors) != protocol.ZONE_COUNT:
            print("avell-rgb: give 1 colour or exactly 4", file=sys.stderr)
            return 2
        client.set_zones(colors)
    elif cmd == "zone":
        client.set_zone(args.zone, args.color)
    elif cmd == "brightness":
        client.set_brightness(args.value)
    elif cmd == "on":
        client.set_power(True)
    elif cmd == "off":
        client.set_power(False)
    elif cmd == "effect":
        options: dict[str, Any] = {}
        if args.speed is not None:
            options["speed"] = args.speed
        if args.palette:
            options["palette"] = args.palette
        if args.direction is not None:
            options["direction"] = args.direction
        if args.allow_unverified:
            options["allow_unverified"] = True
        client.set_effect(args.name, options)
    elif cmd == "identify":
        client.identify_zone(args.zone)
    elif cmd == "profile":
        if args.action == "list":
            for name in client.list_profiles():
                print(name)
        else:
            getattr(client, f"{args.action}_profile")(args.name)
    elif cmd == "software-effect":
        if args.action == "start":
            options = dict(args.option)
            if args.fps is not None:
                options["fps"] = args.fps
            client.start_software_effect(args.name, options)
        elif args.action == "stop":
            client.stop_software_effect()
        else:
            for name in client.list_effects()[1]:
                print(name)
    elif cmd == "save":
        if not args.confirm:
            print(
                "avell-rgb: saving to firmware is EXPERIMENTAL and unverified. "
                "Re-run with --confirm to proceed.",
                file=sys.stderr,
            )
            return 2
        client.save_to_firmware()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from .dbus_client import Client, ClientError

    try:
        return run(args, Client(args.bus))
    except ClientError as exc:
        print(f"avell-rgb: {exc.kind}: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
