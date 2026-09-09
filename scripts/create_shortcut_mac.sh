#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Creates a "Shogun" app bundle on the macOS Desktop
#  or a .desktop file on Linux
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

SHOGUN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OS="$(uname -s)"

case "$OS" in
    Darwin*)
        # ── macOS: Create a minimal .app bundle ──────────────
        APP_PATH="$HOME/Desktop/Shogun.app"
        mkdir -p "$APP_PATH/Contents/MacOS"
        mkdir -p "$APP_PATH/Contents/Resources"

        # Copy icon if available (PNG → simple reference)
        if [ -f "$SHOGUN_DIR/frontend/public/shogun-logo.png" ]; then
            cp "$SHOGUN_DIR/frontend/public/shogun-logo.png" "$APP_PATH/Contents/Resources/shogun-logo.png"
        fi

        # Terminal executes .command files. Quote paths as shell literals so
        # spaces, quotes, dollar signs, and backticks in a home folder are safe.
        COMMAND_PATH="$APP_PATH/Contents/Resources/Shogun.command"
        printf '#!/bin/bash\nexec /bin/bash %q\n' "$SHOGUN_DIR/start.sh" > "$COMMAND_PATH"
        chmod +x "$COMMAND_PATH"
        printf '#!/bin/bash\nexec /usr/bin/open -a Terminal %q\n' "$COMMAND_PATH" > "$APP_PATH/Contents/MacOS/Shogun"
        chmod +x "$APP_PATH/Contents/MacOS/Shogun"

        # Create Info.plist
        cat > "$APP_PATH/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Shogun</string>
    <key>CFBundleDisplayName</key>
    <string>Shogun — The Tenshu</string>
    <key>CFBundleIdentifier</key>
    <string>com.shogun.tenshu</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>Shogun</string>
    <key>CFBundleIconFile</key>
    <string>shogun-logo</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
PLIST

        echo "  ✅  macOS app created: ~/Desktop/Shogun.app"
        echo "     Double-click to launch the Tenshu."
        ;;

    Linux*)
        # ── Linux: Create a .desktop file ────────────────────
        DESKTOP_FILE="$HOME/Desktop/shogun.desktop"
        mkdir -p "$HOME/Desktop"
        ICON_PATH="$SHOGUN_DIR/frontend/public/shogun-logo.png"

        cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Shogun — The Tenshu
Comment=Launch the Shogun AI Agent Framework
Exec=bash "$SHOGUN_DIR/start.sh"
Icon=$ICON_PATH
Terminal=true
Categories=Development;
DESKTOP
        chmod +x "$DESKTOP_FILE"

        # Trust the desktop file (GNOME)
        if command -v gio &>/dev/null; then
            gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
        fi

        echo "  ✅  Desktop shortcut created: ~/Desktop/shogun.desktop"
        echo "     Double-click to launch the Tenshu."
        ;;

    *)
        echo "  ⚠️  Unsupported OS for shortcut creation."
        echo "     You can launch Shogun manually: bash start.sh"
        ;;
esac
