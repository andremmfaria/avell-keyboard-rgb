#!/bin/sh
# Runs after removal. State in /var/lib/avell-keyboard-rgb and the avell-rgb user are kept
# (purge is a manual step, see README).
set -e
if command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload || true
fi
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload || true
fi
exit 0
