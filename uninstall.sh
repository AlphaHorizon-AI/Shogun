#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — Uninstaller (macOS / Linux)
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
GOLD='\033[1;33m'
RED='\033[1;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${RED}  SHOGUN AI Framework - Uninstaller${NC}"
echo "  ======================================================"
echo "  This will completely remove Shogun, including:"
echo "   - All virtual environments"
echo "   - Database files, memories, and keys"
echo "   - Desktop shortcuts"
echo "   - The entirety of this folder"
echo ""
echo -e "${GOLD}  WARNING: Please ensure the server is NOT running.${NC}"
echo "       (Close any other terminals running Shogun)"
echo ""

read -p "  Are you absolutely sure? (Type 'Y' to confirm): " CONFIRM

if [[ "$CONFIRM" != "Y" && "$CONFIRM" != "y" ]]; then
    echo "  Uninstall cancelled."
    exit 0
fi

echo ""
echo "  [+] Removing desktop shortcut..."
if [ "$(uname -s)" = "Darwin" ]; then
    rm -rf "$HOME/Desktop/Shogun.app" 2>/dev/null || true
else
    rm -f "$HOME/Desktop/shogun.desktop" 2>/dev/null || true
fi

echo "  [+] Removing Shogun folder..."
SELF_DIR=$(pwd)
PARENT_DIR=$(dirname "$SELF_DIR")
DIR_NAME=$(basename "$SELF_DIR")

# We must CD out of the folder before we delete it
cd "$PARENT_DIR"

rm -rf "$DIR_NAME" 2>/dev/null || true

echo "  [OK] Shogun has been completely uninstalled."
echo ""
