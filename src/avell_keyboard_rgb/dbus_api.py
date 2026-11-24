"""The D-Bus contract: names and interface XML. Must match docs/dbus-interface.md."""

BUS_NAME = "io.github.andremmfaria.AvellRgb"
OBJECT_PATH = "/io/github/andremmfaria/AvellRgb"
INTERFACE = "io.github.andremmfaria.AvellRgb1"
POLKIT_ACTION = "io.github.andremmfaria.AvellRgb.control"

ERR_INVALID = "io.github.andremmfaria.AvellRgb.Error.InvalidArgument"
ERR_NOT_AUTHORIZED = "io.github.andremmfaria.AvellRgb.Error.NotAuthorized"
ERR_DEVICE = "io.github.andremmfaria.AvellRgb.Error.DeviceUnavailable"
ERR_NOT_FOUND = "io.github.andremmfaria.AvellRgb.Error.NotFound"

# Methods that need no polkit authorisation.
READ_ONLY_METHODS = frozenset({"ListEffects", "ListProfiles", "GetState"})

INTERFACE_XML = """<node>
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
    <method name="ExperimentalSaveToFirmware"/>
    <property name="Version" type="s" access="read"/>
    <property name="DeviceConnected" type="b" access="read"/>
    <property name="Power" type="b" access="read"/>
    <property name="Brightness" type="u" access="read"/>
    <property name="Zones" type="as" access="read"/>
    <property name="Mode" type="s" access="read"/>
    <property name="SoftwareEffect" type="s" access="read"/>
    <signal name="StateChanged"/>
  </interface>
</node>"""
