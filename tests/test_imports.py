"""Import checks with PyGObject made unavailable.

The portable CI job runs the test suite on a Python without PyGObject. These tests pin which
modules must stay importable there and which ones need `gi`.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# Blocking gi through sys.modules makes `import gi` raise ImportError, even when it is installed.
_BLOCK_GI = (
    "import sys; sys.modules['gi'] = None; import importlib; importlib.import_module(sys.argv[1])"
)

GTK_FREE = [
    "avell_keyboard_rgb",
    "avell_keyboard_rgb.protocol",
    "avell_keyboard_rgb.state",
    "avell_keyboard_rgb.effects",
    "avell_keyboard_rgb.hidraw",
    "avell_keyboard_rgb.controller",
    "avell_keyboard_rgb.cli",
    "avell_keyboard_rgb.dbus_api",
]

NEEDS_GI = [
    "avell_keyboard_rgb.dbus_client",
    "avell_keyboard_rgb.dbus_service",
    "avell_keyboard_rgb.daemon",
    "avell_keyboard_rgb.gui.app",
    "avell_keyboard_rgb.gui.window",
]


def _import_without_gi(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_GI, module],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize("module", GTK_FREE)
def test_imports_without_gi(module: str) -> None:
    result = _import_without_gi(module)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("module", NEEDS_GI)
def test_gi_modules_fail_cleanly_without_gi(module: str) -> None:
    result = _import_without_gi(module)
    assert result.returncode != 0
    # A ModuleNotFoundError (an ImportError) about gi, not some unrelated crash.
    assert "ModuleNotFoundError: import of gi halted" in result.stderr


def test_cli_main_does_not_import_gi_for_parsing() -> None:
    code = (
        "import sys; sys.modules['gi'] = None; "
        "from avell_keyboard_rgb import cli; cli.build_parser().parse_args(['status'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr
