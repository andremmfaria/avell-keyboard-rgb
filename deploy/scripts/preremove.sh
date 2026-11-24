#!/bin/sh
# Runs before removal. $1 is "remove"/"upgrade" (deb) or a count of remaining installs (rpm).
set -e
case "${1:-}" in
    upgrade|1|2) exit 0 ;;
esac
if [ -d /run/systemd/system ]; then
    systemctl stop avell-rgbd.service || true
fi
exit 0
