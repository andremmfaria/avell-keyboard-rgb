#!/bin/sh
# Runs after install and upgrade on both Debian family (deb) and Fedora family (rpm) systems.
set -e
if command -v systemd-sysusers >/dev/null 2>&1; then
    systemd-sysusers /usr/lib/sysusers.d/avell-keyboard-rgb.conf || true
fi
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload || true
    udevadm trigger --action=add --subsystem-match=hidraw || true
fi
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
    systemctl reload dbus 2>/dev/null || true
    # Pick up a new version of the daemon if it is already running.
    systemctl try-restart avell-rgbd.service || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
exit 0
