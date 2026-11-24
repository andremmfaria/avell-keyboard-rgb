#!/bin/bash
# Renders the app icon PNGs from the master SVG with cairosvg.
# usage: deploy/render-icons.sh [python]
#   python: an interpreter that can import cairosvg (default: python3).
# cairosvg is not a project dependency. Install it into a throwaway venv, never system Python:
#   python3 -m venv ~/.hermes/cache/scratch/iconvenv
#   ~/.hermes/cache/scratch/iconvenv/bin/pip install cairosvg cffi
#   deploy/render-icons.sh ~/.hermes/cache/scratch/iconvenv/bin/python
set -euo pipefail
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python=${1:-python3}
name=io.github.andremmfaria.AvellRgbGui
svg=$here/$name.svg
for size in 16 32 48 64 128 256 512; do
    out=$here/icons/${size}x${size}
    mkdir -p "$out"
    "$python" -c 'import sys, cairosvg; cairosvg.svg2png(url=sys.argv[1], write_to=sys.argv[2], output_width=int(sys.argv[3]), output_height=int(sys.argv[3]))' \
        "$svg" "$out/$name.png" "$size"
    echo "rendered $out/$name.png"
done
