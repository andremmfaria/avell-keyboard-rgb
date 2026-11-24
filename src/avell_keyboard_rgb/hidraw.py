"""hidraw transport: find the keyboard and send 8 byte feature reports (stdlib only)."""

from __future__ import annotations

import fcntl
import os
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from . import protocol

SYSFS_HIDRAW = Path("/sys/class/hidraw")
DEV_ROOT = Path("/dev")

_IOC_WRITE = 1
_IOC_READ = 2


class DeviceError(Exception):
    """The keyboard is missing or a write failed."""


def hidiocsfeature(length: int) -> int:
    """HIDIOCSFEATURE(len) = _IOC(_IOC_WRITE | _IOC_READ, 'H', 0x06, len)."""
    return ((_IOC_WRITE | _IOC_READ) << 30) | (length << 16) | (ord("H") << 8) | 0x06


def find_device(
    sysfs: Path = SYSFS_HIDRAW,
    dev_root: Path = DEV_ROOT,
) -> Path | None:
    """Return the /dev/hidrawN node of the vendor interface, or None.

    Matches HID_ID in the uevent file. If the report descriptor is readable it must
    also declare usage page 0xFF12, so other interfaces of the same USB device are
    skipped. An unreadable descriptor is accepted.
    """
    try:
        entries = sorted(sysfs.glob("hidraw*"), key=lambda p: (len(p.name), p.name))
    except OSError:
        return None
    for entry in entries:
        try:
            uevent = (entry / "device" / "uevent").read_text(errors="replace")
        except OSError:
            continue
        if protocol.HID_ID_STRING.lower() not in uevent.lower():
            continue
        try:
            descriptor = (entry / "device" / "report_descriptor").read_bytes()
        except OSError:
            descriptor = b""
        if descriptor and protocol.USAGE_PAGE_DESCRIPTOR_BYTES not in descriptor:
            continue
        return dev_root / entry.name
    return None


class HidrawTransport:
    """Writes frames through HIDIOCSFEATURE. Thread safe; writes are serialised.

    `opener`, `closer` and `ioctl` are injectable so tests can use a fake device.
    """

    def __init__(
        self,
        path: Path,
        *,
        opener: Callable[[str, int], int] = os.open,
        closer: Callable[[int], None] = os.close,
        ioctl: Callable[[int, int, bytes], object] = fcntl.ioctl,
    ) -> None:
        self.path = path
        self._opener = opener
        self._closer = closer
        self._ioctl = ioctl
        self._fd: int | None = None
        self._lock = threading.Lock()

    def open(self) -> None:
        with self._lock:
            if self._fd is not None:
                return
            try:
                self._fd = self._opener(str(self.path), os.O_RDWR)
            except OSError as exc:
                raise DeviceError(f"cannot open {self.path}: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._fd is not None:
                try:
                    self._closer(self._fd)
                finally:
                    self._fd = None

    def send(self, frames: Iterable[bytes]) -> None:
        with self._lock:
            if self._fd is None:
                raise DeviceError("device not open")
            for frame in frames:
                if len(frame) != protocol.FRAME_LENGTH:
                    raise DeviceError("refusing to send a frame that is not 8 bytes")
                buf = protocol.REPORT_ID_PREFIX + frame
                try:
                    self._ioctl(self._fd, hidiocsfeature(len(buf)), buf)
                except OSError as exc:
                    raise DeviceError(f"write to {self.path} failed: {exc}") from exc
