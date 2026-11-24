from __future__ import annotations

from pathlib import Path

import pytest

from avell_keyboard_rgb import protocol
from avell_keyboard_rgb.hidraw import DeviceError, HidrawTransport, find_device, hidiocsfeature

GOOD = (
    "DRIVER=hid-generic\nHID_ID=0003:0000048D:0000CE00\nHID_NAME=ITE Tech. Inc. ITE Device(8291)\n"
)
VENDOR_DESC = bytes([0x06, 0x12, 0xFF, 0x09, 0x01, 0xA1, 0x01, 0xC0])
KEYBOARD_DESC = bytes([0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0xC0])


def make_node(root: Path, name: str, uevent: str, descriptor: bytes | None) -> None:
    dev = root / name / "device"
    dev.mkdir(parents=True)
    (dev / "uevent").write_text(uevent)
    if descriptor is not None:
        (dev / "report_descriptor").write_bytes(descriptor)


def test_ioctl_number_matches_kernel_macro() -> None:
    # _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x06, 9) as computed by <linux/hidraw.h> on x86_64
    assert hidiocsfeature(9) == 0xC0094806


def test_finds_vendor_interface(tmp_path: Path) -> None:
    make_node(tmp_path, "hidraw0", "HID_ID=0003:00001234:00005678\n", None)
    make_node(tmp_path, "hidraw1", GOOD, KEYBOARD_DESC)
    make_node(tmp_path, "hidraw2", GOOD, VENDOR_DESC)
    assert find_device(tmp_path, Path("/dev")) == Path("/dev/hidraw2")


def test_accepts_unreadable_descriptor(tmp_path: Path) -> None:
    make_node(tmp_path, "hidraw3", GOOD, None)
    assert find_device(tmp_path, Path("/dev")) == Path("/dev/hidraw3")


def test_not_found(tmp_path: Path) -> None:
    make_node(tmp_path, "hidraw0", "HID_ID=0003:00001234:00005678\n", VENDOR_DESC)
    assert find_device(tmp_path, Path("/dev")) is None
    assert find_device(tmp_path / "missing", Path("/dev")) is None


def test_numeric_ordering(tmp_path: Path) -> None:
    make_node(tmp_path, "hidraw10", GOOD, VENDOR_DESC)
    make_node(tmp_path, "hidraw9", GOOD, VENDOR_DESC)
    assert find_device(tmp_path, Path("/dev")) == Path("/dev/hidraw9")


def test_transport_sends_report_id_prefix_and_ioctl() -> None:
    calls: list[tuple[int, int, bytes]] = []
    t = HidrawTransport(
        Path("/dev/hidraw-x"),
        opener=lambda path, flags: 42,
        closer=lambda fd: None,
        ioctl=lambda fd, req, buf: calls.append((fd, req, buf)),
    )
    t.open()
    t.send([protocol.off_frame()])
    assert calls == [(42, hidiocsfeature(9), b"\x00" + protocol.off_frame())]
    t.close()
    with pytest.raises(DeviceError):
        t.send([protocol.off_frame()])


def test_transport_rejects_wrong_length_and_wraps_oserror() -> None:
    def boom(fd: int, req: int, buf: bytes) -> None:
        raise OSError(5, "I/O error")

    t = HidrawTransport(Path("/x"), opener=lambda p, f: 3, closer=lambda fd: None, ioctl=boom)
    t.open()
    with pytest.raises(DeviceError):
        t.send([b"\x01\x02"])
    with pytest.raises(DeviceError):
        t.send([protocol.off_frame()])


def test_open_failure_is_device_error() -> None:
    def deny(path: str, flags: int) -> int:
        raise PermissionError(13, "denied")

    with pytest.raises(DeviceError):
        HidrawTransport(Path("/x"), opener=deny).open()
