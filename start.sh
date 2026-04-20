#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — Tenshu Launcher (macOS / Linux)
# ═══════════════════════════════════════════════════════════════

set -e

# Navigate to script directory (handles shortcut/symlink launches)
cd "$(dirname "$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")")"

# Colors
GOLD='\033[1;33m'
GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m'

echo ""
echo -e "${GOLD}  ⚔️  SHOGUN — Starting the Tenshu...${NC}"
echo ""

# Check venv
if [ ! -d "venv" ]; then
    echo -e "${RED}  ERROR: Virtual environment not found.${NC}"
    echo "  Please run install.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

# Detect Python
PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_CMD="python"
fi

# Check if frontend is built
if [ ! -f "frontend/dist/index.html" ]; then
    echo "  ⚠️  Frontend not built. Building now..."
    cd frontend && npm run build --silent 2>/dev/null && cd ..
    echo -e "  ${GREEN}✅  Frontend built.${NC}"
fi

# Detect OS for browser open
OS="$(uname -s)"

echo -e "  ${GREEN}🌐  Shogun is starting at http://localhost:8000${NC}"
echo "  📖  Your browser will open automatically."
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

# Open browser after delay (background)
(
    sleep 3
    if [ "$OS" = "Darwin" ]; then
        open "http://localhost:8000" 2>/dev/null || true
    else
        xdg-open "http://localhost:8000" 2>/dev/null || true
    fi
) &

# Start the server (blocking)
$PYTHON_CMD -m shogun
