#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — Uninstaller (macOS / Linux)
# ═══════════════════════════════════════════════════════════════

set -e

# Never remove the caller's working directory when invoked from elsewhere.
SELF_DIR="$(cd -P "$(dirname "$0")" && pwd)"
if [ "$SELF_DIR" = / ] || [ "$SELF_DIR" = "$HOME" ] || \
   [ ! -f "$SELF_DIR/pyproject.toml" ] || [ ! -f "$SELF_DIR/shogun/__main__.py" ]; then
    echo "ERROR: Refusing to remove a directory that is not a Shogun installation." >&2
    exit 1
fi

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
    rm -rf -- "$HOME/Desktop/Shogun.app"
else
    rm -f -- "$HOME/Desktop/shogun.desktop"
fi

echo "  [+] Removing Shogun folder..."
PARENT_DIR=$(dirname "$SELF_DIR")

# We must CD out of the folder before we delete it
cd "$PARENT_DIR"

rm -rf -- "$SELF_DIR"

echo "  [OK] Shogun has been completely uninstalled."
echo ""
