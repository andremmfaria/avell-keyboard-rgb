# Usage

The `avell-rgb` command and the `avell-rgb-gui` window are both clients of the `avell-rgbd` daemon, which talks to the keyboard. See [install.md](install.md) for setting it up and [hardware.md](hardware.md) for what the keyboard can and cannot do. Changing the keyboard needs an active local session, explained in [safety.md](safety.md).

## Concepts

- **Zones.** The keyboard has 4 colour zones, numbered 1 to 4 from far left to far right. Keys are not individually addressable.
- **Colours.** Six hex digits, `rrggbb`, with an optional leading `#`.
- **Brightness.** 0 to 50. 0 is no backlight.
- **Speed.** 0 to 10, higher is faster, default 5. The firmware works the other way round; the software inverts it in one place (see [protocol.md](protocol.md)). Speed 9 and 10 send the same wire value, so they run at the same speed on this firmware: wire speed 0 is invalid and makes effects glitch and stop, so the fastest valid value is used for both. Speed 0 is the slowest; its behaviour on its own is not yet tested (see [hardware.md](hardware.md)).
- **Direction.** 0 to 4. Only wave with 1 (left to right, which is the default for wave) is verified. Other effects default to 0. Other values are accepted but their meaning is unknown.
- **State.** The daemon stores the current state and re-applies it at start, after resume from suspend, and while retrying a missing keyboard (see [troubleshooting.md](troubleshooting.md)). The keyboard forgets its state at power off; the daemon restores it.

## Command line

```text
avell-rgb [--version] [--bus {system,session}] COMMAND ...
```

`--bus session` is for development against a daemon on the session bus (see [development.md](development.md)). `avell-rgb --help` and `avell-rgb COMMAND --help` list everything; there is no man page.

| Command | What it does |
|---|---|
| `status` | Shows daemon version, keyboard connection and device path, power, mode, brightness, zones, the current effect, the software effect and the last error |
| `set RRGGBB [RRGGBB ...]` | Sets the zone colours: 4 colours (zone 1 to 4), or 1 colour for all zones. Switches to static mode |
| `zone ZONE RRGGBB` | Sets one zone (1 to 4) and switches to static mode |
| `brightness VALUE` | Sets brightness 0 to 50. Values outside the range are clamped, with a message on stderr |
| `on` | Turns the backlight on by re-applying the stored state |
| `off` | Turns the backlight off; the colours are kept |
| `effect NAME [options]` | Starts a firmware effect, or `static` to return to plain colours |
| `identify ZONE` | Flashes one zone white about three times, then restores the previous output |
| `profile save NAME` | Saves the whole current state under a name; an existing name is overwritten |
| `profile load NAME` | Loads and applies a profile |
| `profile delete NAME` | Deletes a profile |
| `profile list` | Lists profile names |
| `software-effect start NAME [--fps N] [-o KEY=VALUE ...]` | Starts a daemon driven effect |
| `software-effect stop` | Stops it and returns to the last static state |
| `software-effect list` | Lists software effect names |

Options of `effect`:

| Option | Meaning |
|---|---|
| `NAME` | One of `static`, `breathing`, `wave`, `rainbow`, `flashing`, `gradient` |
| `--speed N` | 0 to 10, higher is faster, default 5. Out of range values are clamped with a message |
| `--palette RRGGBB ...` | Up to 7 colours; if omitted, the firmware palette is used |
| `--direction N` | 0 to 4, see Concepts above. Clamped like speed |
| `--allow-unverified` | Allows `raindrop`, which does nothing on rev 0.02. Not listed in the help |

Examples:

```text
avell-rgb set ff0000 00ff00 0000ff ffffff
avell-rgb set 3366ff
avell-rgb zone 2 ff8800
avell-rgb brightness 30
avell-rgb effect wave --speed 8
avell-rgb effect breathing --palette ff0000 0000ff
avell-rgb effect static
avell-rgb off
avell-rgb profile save work
avell-rgb profile load work
avell-rgb software-effect start cpu-temp -o min_temp=45 -o max_temp=85
avell-rgb software-effect stop
avell-rgb identify 3
avell-rgb status
```

Errors from the daemon are printed as `avell-rgb: KIND: message` and the exit status is 1. Argument errors, such as a bad colour or zone, are rejected by the CLI before anything is sent.

## Effects

Firmware effects run on the keyboard itself: `breathing`, `wave`, `rainbow`, `flashing` and `gradient`. They use a palette of up to 7 colours, sent before the effect starts. Rainbow showed only four colour regions in the hardware test; see [hardware.md](hardware.md). `raindrop` is rejected unless `--allow-unverified` is given.

Software effects run in the daemon, which computes the 4 zone colours and writes them. They never run faster than their `fps` (1 to 20, default 10), identical frames are not re-sent, and they are paused while the backlight is off. Options are given with `-o KEY=VALUE`; a value with commas becomes a list; unknown options are rejected.

| Effect | Behaviour | Options |
|---|---|---|
| `cpu-temp` | The whole keyboard goes green, yellow, red between a minimum and a maximum CPU temperature. Blue if no sensor is found | `min_temp` (default 40, 0 to 120), `max_temp` (default 90, 1 to 130, must be above `min_temp`) |
| `battery` | The 4 zones are a charge bar, in steps of 25 percent. Red below 20, orange below 50, green otherwise. A charging battery makes the top lit zone pulse. Blue if there is no battery | none |
| `fade` | A slow colour cycle; each zone is a quarter of a period behind its neighbour | `period` seconds (default 30, 2 to 3600), `colors` (1 to 16 colours, default red, blue, green) |

Setting colours, setting a firmware effect or running `effect static` stops a running software effect.

## Profiles

A profile is a named snapshot of the whole state: power, brightness, zones, the firmware effect and the software effect. Profiles are stored as JSON files in `/var/lib/avell-keyboard-rgb/profiles`. Names match `[A-Za-z0-9_.-]`, up to 64 characters, and cannot start with a dot.

## GUI

Start `avell-rgb-gui` from the application menu (Avell Keyboard RGB) or a terminal. The window has these parts:

- A keyboard outline with four bands. Click a band to select that zone, then use the colour button to set its colour. The Flash button blinks the selected zone.
- A switch for the backlight and a brightness slider (0 to 50).
- A keyboard effect selector (static colours or a firmware effect) with a speed control (0 slowest, 10 fastest).
- A software effect selector with Start and Stop buttons. The GUI starts the effect with its default options.
- Profiles: a name field to save the current setup, and a list with Load and Delete for each saved profile.
- A banner when the daemon is not running (see [troubleshooting.md](troubleshooting.md)).

The GUI has no controls for the effect palette or direction; use the CLI for those. The GUI has only been smoke tested under Xvfb; nobody has looked at it on screen yet (see [todo.md](../todo.md)).

## Related documentation

- [install.md](install.md): installing the package.
- [hardware.md](hardware.md): limits of the supported keyboard and test results.
- [safety.md](safety.md): ranges, clamping and permissions.
- [troubleshooting.md](troubleshooting.md): when a command fails.
- [dbus-interface.md](dbus-interface.md): the same operations as D-Bus methods.
- [protocol.md](protocol.md): how speed and effects map to frames.
