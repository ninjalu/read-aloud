#!/bin/bash
# Generate ReadAloud/Resources/AppIcon.icns from icon_master.png (1024px).
set -euo pipefail
cd "$(dirname "$0")"

[ -f icon_master.png ] || .venv/bin/python make_icon.py

SET="ReadAloud.iconset"
rm -rf "$SET"; mkdir -p "$SET"

# macOS iconset requires these exact names/sizes.
sips -z 16   16   icon_master.png --out "$SET/icon_16x16.png"      >/dev/null
sips -z 32   32   icon_master.png --out "$SET/icon_16x16@2x.png"   >/dev/null
sips -z 32   32   icon_master.png --out "$SET/icon_32x32.png"      >/dev/null
sips -z 64   64   icon_master.png --out "$SET/icon_32x32@2x.png"   >/dev/null
sips -z 128  128  icon_master.png --out "$SET/icon_128x128.png"    >/dev/null
sips -z 256  256  icon_master.png --out "$SET/icon_128x128@2x.png" >/dev/null
sips -z 256  256  icon_master.png --out "$SET/icon_256x256.png"    >/dev/null
sips -z 512  512  icon_master.png --out "$SET/icon_256x256@2x.png" >/dev/null
sips -z 512  512  icon_master.png --out "$SET/icon_512x512.png"    >/dev/null
cp icon_master.png "$SET/icon_512x512@2x.png"

mkdir -p ReadAloud/Resources
iconutil -c icns "$SET" -o ReadAloud/Resources/AppIcon.icns
rm -rf "$SET"
echo "✓ wrote ReadAloud/Resources/AppIcon.icns"
