from __future__ import annotations

import pytest

from avell_keyboard_rgb import cli


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []  # type: ignore[type-arg]

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        def record(*args):  # type: ignore[no-untyped-def]
            self.calls.append((name, *args))
            if name == "list_profiles":
                return ["a", "b"]
            if name == "get_state":
                return {
                    "version": "1",
                    "device_connected": True,
                    "power": True,
                    "mode": "static",
                    "brightness": 10,
                    "zones": ["ffffff"] * 4,
                }
            return None

        return record


def run(*argv: str) -> tuple[int, FakeClient]:
    args = cli.build_parser().parse_args(argv)
    client = FakeClient()
    return cli.run(args, client), client


def test_set_four_colours() -> None:
    code, c = run("set", "ff0000", "#00ff00", "0000FF", "ffffff")
    assert code == 0
    assert c.calls == [("set_zones", ["ff0000", "00ff00", "0000ff", "ffffff"])]


def test_set_single_colour_fills_all() -> None:
    _, c = run("set", "123456")
    assert c.calls == [("set_zones", ["123456"] * 4)]


def test_set_wrong_count() -> None:
    code, c = run("set", "111111", "222222")
    assert code == 2 and c.calls == []


def test_brightness_clamped(capsys: pytest.CaptureFixture[str]) -> None:
    _, c = run("brightness", "99")
    assert c.calls == [("set_brightness", 50)]
    assert "clamped" in capsys.readouterr().err


def test_effect_options() -> None:
    _, c = run("effect", "wave", "--speed", "5", "--palette", "ff0000", "00ff00")
    assert c.calls == [("set_effect", "wave", {"speed": 5, "palette": ["ff0000", "00ff00"]})]


def test_software_effect_options() -> None:
    _, c = run(
        "software-effect",
        "start",
        "fade",
        "--fps",
        "5",
        "-o",
        "period=60",
        "-o",
        "colors=ff0000,0000ff",
    )
    assert c.calls == [
        ("start_software_effect", "fade", {"period": 60, "colors": ["ff0000", "0000ff"], "fps": 5})
    ]


def test_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    _, c = run("profile", "save", "x")
    assert c.calls == [("save_profile", "x")]
    run("profile", "list")
    assert capsys.readouterr().out.split() == ["a", "b"]


def test_save_needs_confirm() -> None:
    code, c = run("save")
    assert code == 2 and c.calls == []
    code, c = run("save", "--confirm")
    assert code == 0 and c.calls == [("save_to_firmware",)]


@pytest.mark.parametrize(
    "argv", [("zone", "5", "ffffff"), ("zone", "1", "nothex"), ("effect", "strobe")]
)
def test_bad_args_exit_2(argv: tuple[str, ...]) -> None:
    with pytest.raises(SystemExit) as info:
        cli.build_parser().parse_args(argv)
    assert info.value.code == 2


def test_status_output(capsys: pytest.CaptureFixture[str]) -> None:
    run("status")
    assert "connected" in capsys.readouterr().out


def test_effect_help_lists_no_raindrop(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["effect", "--help"])
    out = capsys.readouterr().out
    assert "{static,breathing,wave,rainbow,flashing,gradient}" in out


def test_effect_allow_unverified_is_forwarded() -> None:
    _, c = run("effect", "raindrop", "--allow-unverified")
    assert c.calls == [("set_effect", "raindrop", {"allow_unverified": True})]
