#!/bin/sh
# Runs after removal. State in /var/lib/avell-keyboard-rgb and the avell-rgb user are kept
# (purge is a manual step, see docs/install.md).
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload || true
fi
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
exit 0
