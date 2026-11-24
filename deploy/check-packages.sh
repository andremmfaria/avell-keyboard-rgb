#!/bin/bash
# Checks the built .deb and .rpm: payload paths and modes, dependency names, maintainer scripts.
# usage: deploy/check-packages.sh <dir holding the .deb and .rpm>
set -euo pipefail
dir=${1:?usage: check-packages.sh <package dir>}
deb=$(ls "$dir"/*.deb)
rpm=$(ls "$dir"/*.rpm)
fail=0
need() { # need <label> <haystack> <pattern>
    if grep -Eq -- "$3" <<<"$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi
}

contents=$(dpkg-deb -c "$deb")
need "deb launcher is 0755" "$contents" '^-rwxr-xr-x .* \./usr/bin/avell-rgb$'
need "deb daemon launcher is 0755" "$contents" '^-rwxr-xr-x .* \./usr/bin/avell-rgbd$'
need "deb gui launcher is 0755" "$contents" '^-rwxr-xr-x .* \./usr/bin/avell-rgb-gui$'
need "deb ships the python package" "$contents" '\./usr/lib/avell-keyboard-rgb/avell_keyboard_rgb/protocol\.py$'
if grep -q __pycache__ <<<"$contents"; then echo "FAIL deb has no bytecode"; fail=1; else echo "ok   deb has no bytecode"; fi
need "deb unit is 0644" "$contents" '^-rw-r--r-- .* \./usr/lib/systemd/system/avell-rgbd\.service$'
need "deb udev rule is 0644" "$contents" '^-rw-r--r-- .* \./usr/lib/udev/rules\.d/99-avell-keyboard-rgb\.rules$'
need "deb sysusers is 0644" "$contents" '\./usr/lib/sysusers\.d/avell-keyboard-rgb\.conf$'
need "deb dbus policy" "$contents" '\./usr/share/dbus-1/system\.d/io\.github\.andremmfaria\.AvellRgb\.conf$'
need "deb dbus activation" "$contents" '\./usr/share/dbus-1/system-services/io\.github\.andremmfaria\.AvellRgb\.service$'
need "deb polkit policy" "$contents" '\./usr/share/polkit-1/actions/io\.github\.andremmfaria\.AvellRgb\.policy$'
need "deb desktop file" "$contents" '\./usr/share/applications/io\.github\.andremmfaria\.AvellRgbGui\.desktop$'
need "deb icon" "$contents" '\./usr/share/icons/hicolor/scalable/apps/io\.github\.andremmfaria\.AvellRgbGui\.svg$'
for size in 16 32 48 64 128 256 512; do
    need "deb icon ${size}x${size}" "$contents" "\\./usr/share/icons/hicolor/${size}x${size}/apps/io\\.github\\.andremmfaria\\.AvellRgbGui\\.png\$"
done
need "deb is arch all" "$(dpkg-deb -f "$deb" Architecture)" '^all$'
deb_depends=$(dpkg-deb -f "$deb" Depends)
for dep in python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 dbus systemd; do
    need "deb depends on $dep" "$deb_depends" "(^|, )$dep(,|\$| )"
done
for script in postinst prerm postrm; do
    need "deb has $script" "$(dpkg-deb -I "$deb")" "^ +[0-9]+ bytes, +[0-9]+ lines +\\*  $script "
done

if ! command -v rpm >/dev/null; then
    echo "skip rpm checks (rpm not found)"
    exit "$fail"
fi
rpm_files=$(rpm -qplv "$rpm")
need "rpm launcher is 0755" "$rpm_files" '^-rwxr-xr-x .* /usr/bin/avell-rgb$'
need "rpm ships the python package" "$rpm_files" '/usr/lib/avell-keyboard-rgb/avell_keyboard_rgb/protocol\.py$'
need "rpm unit is 0644" "$rpm_files" '^-rw-r--r-- .* /usr/lib/systemd/system/avell-rgbd\.service$'
need "rpm udev rule is 0644" "$rpm_files" '^-rw-r--r-- .* /usr/lib/udev/rules\.d/99-avell-keyboard-rgb\.rules$'
need "rpm dbus policy" "$rpm_files" '/usr/share/dbus-1/system\.d/io\.github\.andremmfaria\.AvellRgb\.conf$'
need "rpm polkit policy" "$rpm_files" '/usr/share/polkit-1/actions/io\.github\.andremmfaria\.AvellRgb\.policy$'
need "rpm icon svg" "$rpm_files" '/usr/share/icons/hicolor/scalable/apps/io\.github\.andremmfaria\.AvellRgbGui\.svg$'
for size in 16 32 48 64 128 256 512; do
    need "rpm icon ${size}x${size}" "$rpm_files" "/usr/share/icons/hicolor/${size}x${size}/apps/io\\.github\\.andremmfaria\\.AvellRgbGui\\.png\$"
done
need "rpm is noarch" "$(rpm -qp --queryformat '%{ARCH}' "$rpm")" '^noarch$'
rpm_requires=$(rpm -qpR "$rpm")
for dep in python3-gobject gtk4 libadwaita dbus-daemon polkit systemd; do
    need "rpm requires $dep" "$rpm_requires" "^$dep"
done
need "rpm post-install reloads udev" "$(rpm -qp --scripts "$rpm")" 'udevadm control --reload'
exit "$fail"
