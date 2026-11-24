#!/bin/bash
# Static checks of the deploy files; needs no root and no hardware.
# - shell syntax of the launchers and maintainer scripts (and shellcheck when installed)
# - the udev rule: syntax (udevadm verify), never world-writable
# - systemd-analyze verify of the unit, plus the hardening keys the unit must keep
# - the D-Bus policy, polkit policy and desktop file (xmllint, desktop-file-validate when installed)
# - nfpm.yaml references only files that exist
# usage: deploy/check-deploy.sh
set -uo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo=$(dirname "$here")
fail=0
ok() { echo "ok   $1"; }
bad() { echo "FAIL $1"; fail=1; }
run() { # run <label> <command...>
    local label=$1
    shift
    if "$@" >/dev/null 2>&1; then ok "$label"; else bad "$label"; fi
}

scripts=("$here"/bin/* "$here"/scripts/*.sh "$here"/check-deploy.sh "$here"/check-packages.sh)
for script in "${scripts[@]}"; do
    run "$(basename "$script") passes sh -n" bash -n "$script"
done
if command -v shellcheck >/dev/null; then
    run "shellcheck of the shell files" shellcheck "${scripts[@]}"
else
    echo "skip shellcheck (not found)"
fi

# --- udev ---------------------------------------------------------------------
rules=$here/99-avell-keyboard-rgb.rules
if grep -Eq 'MODE="[0-7]?[0-7][0-7][2367]"' "$rules"; then
    bad "udev rule is not world-writable"
else
    ok "udev rule is not world-writable"
fi
if grep -q 'MODE="0660"' "$rules" && grep -q 'GROUP="avell-rgb"' "$rules"; then
    ok "udev rule uses group avell-rgb mode 0660"
else
    bad "udev rule uses group avell-rgb mode 0660"
fi
if command -v udevadm >/dev/null; then
    # The avell-rgb group exists only after the package is installed, so verify a copy that
    # names root instead.
    vtmp=$(mktemp -d)
    sed 's/GROUP="avell-rgb"/GROUP="root"/' "$rules" >"$vtmp/99-avell-keyboard-rgb.rules"
    run "udevadm verify" udevadm verify "$vtmp/99-avell-keyboard-rgb.rules"
    rm -rf "$vtmp"
else
    echo "skip udevadm verify (not found)"
fi

# --- systemd ------------------------------------------------------------------
unit=$here/avell-rgbd.service
for key in NoNewPrivileges=yes ProtectSystem=strict ProtectHome=yes PrivateNetwork=yes \
    'CapabilityBoundingSet=$' DevicePolicy=closed DeviceAllow=char-hidraw User=avell-rgb; do
    if grep -Eq "^$key" "$unit"; then ok "unit has $key"; else bad "unit has $key"; fi
done
if command -v systemd-analyze >/dev/null; then
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    mkdir -p "$tmp/bin"
    printf '#!/bin/sh\n' >"$tmp/bin/avell-rgbd"
    chmod 755 "$tmp/bin/avell-rgbd"
    sed "s#=/usr/bin/#=$tmp/bin/#" "$unit" >"$tmp/avell-rgbd.service"
    out=$(systemd-analyze verify --man=no "$tmp/avell-rgbd.service" 2>&1)
    status=$?
    # The unit names a user that exists only after the package is installed.
    if [ "$status" -eq 0 ] && ! grep -Eq 'not executable|Failed to|Unknown key|Unknown section' <<<"$out"; then
        ok "systemd-analyze verify"
    else
        bad "systemd-analyze verify"
        echo "$out"
    fi
else
    echo "skip systemd-analyze verify (not found)"
fi

# --- XML and desktop files ----------------------------------------------------
if command -v xmllint >/dev/null; then
    for f in "$here"/*.conf "$here"/*.policy "$here"/*.svg; do
        run "xmllint $(basename "$f")" xmllint --noout --nonet "$f"
    done
else
    echo "skip xmllint (not found)"
fi
if command -v desktop-file-validate >/dev/null; then
    run "desktop-file-validate" desktop-file-validate "$here"/*.desktop
else
    echo "skip desktop-file-validate (not found)"
fi

# --- nfpm.yaml sources exist ----------------------------------------------------
missing=0
while read -r src; do
    if [ ! -e "$repo/$src" ]; then
        echo "missing nfpm source: $src"
        missing=1
    fi
done < <(sed -n 's/^ *- src: *//p; s/^ *\(postinstall\|preremove\|postremove\): *//p' "$repo/nfpm.yaml")
if [ "$missing" -eq 0 ]; then ok "nfpm.yaml sources exist"; else bad "nfpm.yaml sources exist"; fi

exit "$fail"
