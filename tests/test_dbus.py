"""D-Bus layer tests against a private dbus-daemon and the real Service with a fake keyboard."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("gi")

from avell_keyboard_rgb import cli, dbus_api  # noqa: E402
from avell_keyboard_rgb.dbus_client import Client, ClientError, Gio, GLib  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("dbus-daemon") is None, reason="dbus-daemon missing")


def test_docs_xml_matches_exported_xml() -> None:
    text = (ROOT / "docs" / "dbus-interface.md").read_text()
    match = re.search(r"```xml\n(.*?)```", text, re.S)
    assert match is not None
    assert match.group(1).strip() == dbus_api.INTERFACE_XML.strip()


class Env:
    def __init__(self, tmp: Path, address: str) -> None:
        self.state_dir = tmp / "state"
        self.frames_file = tmp / "frames.txt"
        self.address = address

    def frames(self) -> list[str]:
        if not self.frames_file.exists():
            return []
        return self.frames_file.read_text().split()

    def clear(self) -> None:
        self.frames_file.unlink(missing_ok=True)


def _start(tmp: Path, address: str, *extra: str) -> subprocess.Popen[str]:
    env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=address, PYTHONPATH=f"{ROOT}:{ROOT / 'src'}")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.dbus_server_helper",
            str(tmp / "state"),
            str(tmp / "frames.txt"),
            *extra,
        ],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        cwd=ROOT,
    )
    assert proc.stdout is not None
    assert proc.stdout.readline().strip() == "ready"
    return proc


@pytest.fixture(scope="module")
def bus_address() -> Iterator[str]:
    daemon = subprocess.Popen(
        ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert daemon.stdout is not None
    address = daemon.stdout.readline().strip()
    yield address
    daemon.terminate()
    daemon.wait()


@pytest.fixture(scope="module")
def env(bus_address: str, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Env]:
    tmp = tmp_path_factory.mktemp("dbus")
    proc = _start(tmp, bus_address)
    yield Env(tmp, bus_address)
    proc.terminate()
    proc.wait()


def connect(address: str) -> Gio.DBusConnection:
    # A private connection: the process-wide session bus is never touched, so the GUI tests
    # that run later in the same process are not affected by this throwaway bus.
    return Gio.DBusConnection.new_for_address_sync(
        address,
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
        | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None,
        None,
    )


@pytest.fixture(scope="module")
def conn(env: Env) -> Iterator[Gio.DBusConnection]:
    connection = connect(env.address)
    yield connection
    connection.close_sync(None)


@pytest.fixture
def client(env: Env, conn: Gio.DBusConnection) -> Client:
    env.clear()
    return Client(connection=conn)


def test_set_zones_and_state(client: Client, env: Env) -> None:
    client.set_zones(["ff0000", "00ff00", "0000ff", "ffffff"])
    frames = env.frames()
    assert frames[0] == "140001ff00000000"
    assert frames[4].startswith("080201")
    state = client.get_state()
    assert state["zones"] == ["ff0000", "00ff00", "0000ff", "ffffff"]
    assert state["device_connected"] is True
    assert state["mode"] == "static"


def test_properties(client: Client) -> None:
    client.set_brightness(33)
    reply = client.connection.call_sync(
        dbus_api.BUS_NAME,
        dbus_api.OBJECT_PATH,
        "org.freedesktop.DBus.Properties",
        "GetAll",
        GLib.Variant("(s)", (dbus_api.INTERFACE,)),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
    )
    props = reply.unpack()[0]
    assert props["Brightness"] == 33
    assert set(props) == {
        "Version",
        "DeviceConnected",
        "Power",
        "Brightness",
        "Zones",
        "Mode",
        "SoftwareEffect",
    }


def test_effect_and_profiles(client: Client, env: Env) -> None:
    client.set_effect("wave", {"speed": 4, "palette": ["ff0000", "0000ff"]})
    assert env.frames()[-1].startswith("08020306")
    client.save_profile("wavy")
    client.set_zones(["000000"] * 4)
    assert "wavy" in client.list_profiles()
    client.load_profile("wavy")
    assert client.get_state()["mode"] == "wave"
    client.delete_profile("wavy")
    with pytest.raises(ClientError) as info:
        client.load_profile("wavy")
    assert info.value.kind == "NotFound"


def test_invalid_arguments_map_to_error(client: Client) -> None:
    for call in (
        lambda: client.set_zone(9, "ffffff"),
        lambda: client.set_brightness(51),
        lambda: client.set_zones(["zzzzzz"] * 4),
        lambda: client.set_effect("wave", {"speed": 11}),
        lambda: client.save_profile("../etc"),
    ):
        with pytest.raises(ClientError) as info:
            call()
        assert info.value.kind == "InvalidArgument"


def test_raindrop_rejected_over_bus_unless_allowed(client: Client, env: Env) -> None:
    before = env.frames()
    with pytest.raises(ClientError) as info:
        client.set_effect("raindrop", {})
    assert info.value.kind == "InvalidArgument"
    assert "unsupported" in str(info.value)
    assert env.frames() == before  # nothing was sent
    client.set_effect("raindrop", {"allow_unverified": True})
    assert env.frames()[-1].startswith("08020a")
    assert "raindrop" not in client.list_effects()[0]


def test_software_effect_over_bus(client: Client, env: Env) -> None:
    client.start_software_effect("fade", {"fps": 20, "period": 4})
    assert client.get_state()["software_effect"] == "fade"
    client.stop_software_effect()
    assert client.get_state()["software_effect"] == ""
    firmware, software = client.list_effects()
    assert "wave" in firmware and "fade" in software


def run_cli(client: Client, *argv: str) -> int:
    return cli.run(cli.build_parser().parse_args(["--bus", "session", *argv]), client)


def test_cli_against_daemon(client: Client, capsys: pytest.CaptureFixture[str]) -> None:
    assert run_cli(client, "set", "ff0000", "00ff00", "0000ff", "ffffff") == 0
    assert run_cli(client, "effect", "wave", "--speed", "5") == 0
    assert run_cli(client, "brightness", "99") == 0
    assert run_cli(client, "status") == 0
    out = capsys.readouterr().out
    assert "brightness     : 50 / 50" in out
    assert "mode           : wave" in out
    assert run_cli(client, "zone", "2", "00ffff") == 0


def test_denied_caller_gets_not_authorized(bus_address: str, tmp_path: Path) -> None:
    # A second daemon cannot share the name, so stop the module one by using another bus.
    daemon = subprocess.Popen(
        ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert daemon.stdout is not None
    address = daemon.stdout.readline().strip()
    proc = _start(tmp_path, address, "--deny")
    try:
        denied = Client(connection=connect(address))
        with pytest.raises(ClientError) as info:
            denied.set_brightness(10)
        assert info.value.kind == "NotAuthorized"
        assert denied.get_state()["brightness"] == 25  # read only calls still work
    finally:
        proc.terminate()
        proc.wait()
        daemon.terminate()
        daemon.wait()
