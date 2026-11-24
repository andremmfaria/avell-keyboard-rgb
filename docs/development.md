# Development

The open items and roadmap are in [todo.md](../todo.md). Install and runtime details for users are in [install.md](install.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/avell_keyboard_rgb/protocol.py` | All wire constants and frame builders, including the speed inversion |
| `src/avell_keyboard_rgb/hidraw.py` | Device discovery and the `HIDIOCSFEATURE` ioctl |
| `src/avell_keyboard_rgb/state.py` | State model, validation and the store for the state file and profiles |
| `src/avell_keyboard_rgb/effects.py` | Software effects and the engine that paces them |
| `src/avell_keyboard_rgb/controller.py` | Daemon logic without D-Bus |
| `src/avell_keyboard_rgb/dbus_api.py`, `dbus_service.py`, `daemon.py` | The D-Bus contract, the service and the `avell-rgbd` entry point |
| `src/avell_keyboard_rgb/dbus_client.py`, `cli.py`, `gui/` | The clients: shared D-Bus client, `avell-rgb` and `avell-rgb-gui` |
| `deploy/` | Launchers, systemd unit, udev rule, sysusers file, D-Bus and polkit files, desktop entry, icons, maintainer scripts and the deploy checks |
| `docs/` | This documentation |
| `tests/` | The test suite; `tests/hardware/` holds the interactive hardware test |
| `nfpm.yaml` | The definition of both packages |
| `.github/workflows/` | CI, packaging and tagging workflows |

The D-Bus contract is in [dbus-interface.md](dbus-interface.md) and the wire protocol in [protocol.md](protocol.md).

## Development setup

PyGObject comes from the distribution, so the virtual environment uses system site packages.

```text
uv venv --system-site-packages --python /usr/bin/python3 .venv
uv pip install --python .venv/bin/python pytest ruff mypy
uv pip install --python .venv/bin/python --no-deps -e .
```

The `dev` extra in `pyproject.toml` lists the same tools.

Run the daemon on a private session bus without a keyboard or root, then use the CLI against it:

```text
avell-rgbd --bus session --no-polkit --state-dir /tmp/avell-state
avell-rgb --bus session status
```

The daemon reports the keyboard as not found and retries. `--no-polkit` is refused on the system bus.

## Tests and checks

```text
xvfb-run -a .venv/bin/pytest -q -p no:warnings
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src tests
deploy/check-deploy.sh
```

The suite uses a fake keyboard and a private D-Bus daemon, so no hardware or root is needed. The GUI tests need a display, which `xvfb-run` provides, and skip without one. Tests use an allow-all authorizer, so they cannot show polkit problems on a real install; `tests/test_deploy_policy.py` and `deploy/check-deploy.sh` guard the owner annotation instead (see [safety.md](safety.md)). `tests/test_imports.py` pins which modules must import without PyGObject, and `tests/test_docs_links.py` checks the links in the Markdown files.

`deploy/check-deploy.sh` checks shell syntax (and shellcheck when installed), the udev rule, the systemd unit and its hardening keys, the polkit owner annotation, the XML and desktop files, the icons, and that every source in `nfpm.yaml` exists. Tools that are not installed are skipped with a message.

## Hardware test

`tests/hardware/hw-test-installed.py` is an interactive script for a laptop with the real keyboard. See [../tests/hardware/README.md](../tests/hardware/README.md). The results so far are in [hardware.md](hardware.md). Update `docs/protocol.md` (verified or unverified, with the evidence file name) and the constants in `protocol.py` from what a run shows, and nowhere else.

## Protocol rules

- Protocol constants live in `protocol.py` only. Everything above it uses user values (speed 0 to 10, higher is faster).
- The code was written from public protocol facts and the project's own hardware test. No code is copied from ite8291r3-ctl or tuxedo-drivers, which are GPL licensed.
- Firmware writes are not implemented and must not be added (see [safety.md](safety.md)).

## Packaging

One `nfpm.yaml` builds an architecture independent `.deb` and `.rpm`. The code is installed under `/usr/lib/avell-keyboard-rgb` with launchers that set `PYTHONPATH` (see [install.md](install.md)). The documentation is installed to `/usr/share/doc/avell-keyboard-rgb/`. Build locally with nfpm:

```text
VERSION=0.1.2 nfpm package --packager deb --target dist/
VERSION=0.1.2 nfpm package --packager rpm --target dist/
deploy/check-packages.sh dist
```

`deploy/check-packages.sh` inspects the built packages: payload paths and modes, the documentation files, dependency names and maintainer scripts. It needs `dpkg-deb`, and runs the rpm checks only if `rpm` is installed. When you add a file to `docs/`, add it to `nfpm.yaml` and to the list in `check-packages.sh`.

## Continuous integration and releases

| Workflow | Runs | Does |
|---|---|---|
| `ci.yml` (CI) | Push and pull requests to main | Job `test`: ruff format and check, mypy, `deploy/check-deploy.sh` and pytest under Xvfb. Job `portable`: pytest on Python 3.10 to 3.14 without PyGObject |
| `package.yml` (Package) | Called by Tag Release, on `v*` tags, and manually | Builds the `.deb` and `.rpm` with nfpm, runs `deploy/check-packages.sh`, lints the `.deb` with lintian (informational), uploads artifacts and attaches both files to the GitHub release |
| `tag-release.yml` (Tag Release) | Every push to main | Reads the version from `pyproject.toml`, creates or force-moves the tag `v<version>` to the new commit, then calls Package |

Releasing: change `version` in `pyproject.toml` and push to main. Tag Release creates the new `v<version>` tag, and Package builds and attaches the packages. If the version is unchanged, a push to main moves the existing tag to the new commit and rebuilds that release's assets in place. Update the `VERSION=` examples in `nfpm.yaml` and this page when you bump.

## Icons

The master icon is `deploy/io.github.andremmfaria.AvellRgbGui.svg`. The PNGs from 16 to 512 pixels in `deploy/icons/` are generated from it with `deploy/render-icons.sh <python>`, where the interpreter can import cairosvg, and are committed. cairosvg is not a project dependency; install it into a throwaway virtual environment, as the script header describes. `nfpm.yaml` installs the SVG and the PNGs into the hicolor theme.

## Related documentation

- [../tests/hardware/README.md](../tests/hardware/README.md): the interactive hardware test.
- [../todo.md](../todo.md): open items and roadmap.
- [protocol.md](protocol.md): the protocol and the evidence for it.
- [dbus-interface.md](dbus-interface.md): the daemon contract.
- [install.md](install.md): what the package installs.
- [safety.md](safety.md): permissions and what is never sent.
- [hardware.md](hardware.md): hardware results.
- [troubleshooting.md](troubleshooting.md): running into problems on an installed system.
