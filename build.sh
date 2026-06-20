#!/bin/bash
# Build Read Aloud into a runnable macOS .app bundle using swiftc (no full Xcode needed).
set -euo pipefail
cd "$(dirname "$0")"

APP="build/ReadAloud.app"
CONTENTS="$APP/Contents"
SDK="$(xcrun --show-sdk-path --sdk macosx)"

echo "→ Cleaning previous build"
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"

echo "→ Compiling Swift sources"
swiftc -O \
  -target arm64-apple-macos14.0 \
  -sdk "$SDK" \
  ReadAloud/Sources/*.swift \
  -o "$CONTENTS/MacOS/ReadAloud"

echo "→ Bundling resources"
cp ReadAloud/Resources/Readability.js "$CONTENTS/Resources/"

echo "→ Writing Info.plist"
cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>            <string>Read Aloud</string>
  <key>CFBundleDisplayName</key>     <string>Read Aloud</string>
  <key>CFBundleIdentifier</key>      <string>com.readaloud.app</string>
  <key>CFBundleExecutable</key>      <string>ReadAloud</string>
  <key>CFBundlePackageType</key>     <string>APPL</string>
  <key>CFBundleShortVersionString</key> <string>1.0</string>
  <key>CFBundleVersion</key>         <string>1</string>
  <key>LSMinimumSystemVersion</key>  <string>14.0</string>
  <key>NSHighResolutionCapable</key> <true/>
  <key>NSPrincipalClass</key>        <string>NSApplication</string>
  <key>NSAppTransportSecurity</key>
  <dict><key>NSAllowsArbitraryLoads</key><true/></dict>
</dict>
</plist>
PLIST

echo "→ Ad-hoc code signing"
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || echo "  (codesign skipped)"

echo "✓ Built $APP"
echo "  Run with:  open $APP   (or ./build.sh run)"

if [ "${1:-}" = "run" ]; then
  echo "→ Launching"
  open "$APP"
fi
