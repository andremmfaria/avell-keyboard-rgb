# D-Bus interface

This is the contract between the daemon (`avell-rgbd`) and its clients (`avell-rgb`, `avell-rgb-gui`, anything else). It is independent of the implementation language: the daemon could be rewritten without touching the clients. A test checks that the XML below is identical to the one the daemon exports.

## Names

| Item | Value |
|---|---|
| Bus | system bus (`--bus session` exists for development and tests only) |
| Well-known name | `io.github.andremmfaria.AvellRgb` |
| Object path | `/io/github/andremmfaria/AvellRgb` |
| Interface | `io.github.andremmfaria.AvellRgb1` |
| Polkit action | `io.github.andremmfaria.AvellRgb.control` |

## Conventions

- Colours are strings of six hex digits, `rrggbb`, with an optional leading `#`. The daemon always returns them lower case without `#`.
- The keyboard has 4 zones. Zone numbers are 1 to 4, left to right.
- Brightness is 0 to 50. Speed is 0 to 10. Out of range values are rejected with `io.github.andremmfaria.AvellRgb.Error.InvalidArgument`; they are never clamped silently on the bus (the CLI and GUI clamp before sending).
- Profile names match `[A-Za-z0-9_.-]{1,64}` and may not start with a dot.
- Read-only members (properties, `List*`, `GetState`) need no authorisation. Every method that changes state or the device is authorised with polkit action `io.github.andremmfaria.AvellRgb.control`, which is granted without a prompt to the active local session and denied otherwise.

## Interface XML

```xml
<node>
  <interface name="io.github.andremmfaria.AvellRgb1">
    <method name="SetZones">
      <arg type="as" name="colors" direction="in"/>
    </method>
    <method name="SetZone">
      <arg type="u" name="zone" direction="in"/>
      <arg type="s" name="color" direction="in"/>
    </method>
    <method name="SetBrightness">
      <arg type="u" name="brightness" direction="in"/>
    </method>
    <method name="SetPower">
      <arg type="b" name="on" direction="in"/>
    </method>
    <method name="SetEffect">
      <arg type="s" name="name" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
    </method>
    <method name="IdentifyZone">
      <arg type="u" name="zone" direction="in"/>
    </method>
    <method name="StartSoftwareEffect">
      <arg type="s" name="name" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
    </method>
    <method name="StopSoftwareEffect"/>
    <method name="ListEffects">
      <arg type="as" name="firmware" direction="out"/>
      <arg type="as" name="software" direction="out"/>
    </method>
    <method name="SaveProfile">
      <arg type="s" name="name" direction="in"/>
    </method>
    <method name="LoadProfile">
      <arg type="s" name="name" direction="in"/>
    </method>
    <method name="DeleteProfile">
      <arg type="s" name="name" direction="in"/>
    </method>
    <method name="ListProfiles">
      <arg type="as" name="names" direction="out"/>
    </method>
    <method name="GetState">
      <arg type="a{sv}" name="state" direction="out"/>
    </method>
    <property name="Version" type="s" access="read"/>
    <property name="DeviceConnected" type="b" access="read"/>
    <property name="Power" type="b" access="read"/>
    <property name="Brightness" type="u" access="read"/>
    <property name="Zones" type="as" access="read"/>
    <property name="Mode" type="s" access="read"/>
    <property name="SoftwareEffect" type="s" access="read"/>
    <signal name="StateChanged"/>
  </interface>
</node>
```

## Methods

| Method | Behaviour |
|---|---|
| `SetZones(as colors)` | Exactly 4 colours, zone 1 to 4. Switches to static (direct) mode, stops any software effect. |
| `SetZone(u zone, s color)` | Changes one zone and switches to static mode, stops any software effect. |
| `SetBrightness(u)` | 0 to 50. Applies to static mode, firmware effects and software effects. |
| `SetPower(b)` | `false` sends the off frame and keeps the colour state; `true` re-applies the stored state. A running software effect is paused while off. |
| `SetEffect(s name, a{sv} options)` | Starts a firmware effect: `breathing`, `wave`, `rainbow`, `flashing`, `gradient`. Option keys: `speed` (u, 0 to 10, default 5, higher is faster; the inversion the firmware needs is done inside the daemon), `palette` (as, up to 7 colours, default is the firmware palette), `direction` (u, 0 to 4; the default is 1 for `wave`, which moves left to right and is verified, and 0 for the others; other values are unverified), `allow_unverified` (b, default false). `raindrop` did nothing on ITE 8291 rev 0.02 in the hardware test, so it is not listed by `ListEffects` and is rejected with `InvalidArgument` (message says it is unsupported) unless `allow_unverified` is true; with the flag the frame is sent as is, with no promise it does anything. Use `static` as the name to go back to static colours. Stops any software effect. |
| `IdentifyZone(u zone)` | Flashes the given zone about three times in white, then restores the previous output. |
| `StartSoftwareEffect(s name, a{sv} options)` | Starts a daemon driven effect: `cpu-temp`, `battery`, `fade`. Common option `fps` (u, 1 to 20, default 10). Others are per effect and documented in the CLI help. |
| `StopSoftwareEffect()` | Stops the software effect and returns to the last static state. |
| `ListEffects()` | Returns the firmware and software effect names. |
| `SaveProfile(s)` / `LoadProfile(s)` / `DeleteProfile(s)` / `ListProfiles()` | Named snapshots of the whole state (power, brightness, zones, effect, software effect) stored under `/var/lib/avell-keyboard-rgb/profiles`. Saving an existing name overwrites it. Loading applies it at once. |
| `GetState()` | Returns the same data as the properties plus `effect` options, `software_options`, `device_path` and `last_error`, as `a{sv}`. |

## Properties and signals

All properties are read only. `Mode` is `static`, `off` or a firmware effect name. `SoftwareEffect` is the empty string when none runs. `StateChanged` is emitted after any change; clients should then re-read the properties or call `GetState`. `org.freedesktop.DBus.Properties.PropertiesChanged` is emitted as well.

## Errors

| Error name | Meaning |
|---|---|
| `io.github.andremmfaria.AvellRgb.Error.InvalidArgument` | Bad colour, zone, range, name or option. |
| `io.github.andremmfaria.AvellRgb.Error.NotAuthorized` | Polkit denied the caller. |
| `io.github.andremmfaria.AvellRgb.Error.DeviceUnavailable` | The keyboard was not found or the write failed. The state is still stored and will be applied when the device returns. |
| `io.github.andremmfaria.AvellRgb.Error.NotFound` | Unknown profile. |

## Daemon behaviour that clients can rely on

- Writes to the keyboard are serialised; clients never see interleaved frames.
- State is stored in `/var/lib/avell-keyboard-rgb/state.json` and re-applied when the daemon starts, after resume from suspend (logind `PrepareForSleep(false)`), and retried every 5 seconds while the keyboard is missing or a write failed.
- Software effects never run faster than their `fps`, and identical frames are not re-sent.

## Related documentation

- [usage.md](usage.md): the CLI and GUI, which are clients of this interface.
- [protocol.md](protocol.md): the frames the daemon sends for these calls.
- [safety.md](safety.md): the polkit action and the permissions model.
- [development.md](development.md): the repository layout and tests, including the check of the XML above.
- [hardware.md](hardware.md): which effects and options are verified.
