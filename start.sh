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
VENV_DIR=""
if [ -d "venv" ]; then
    VENV_DIR="venv"
elif [ -d ".venv" ]; then
    VENV_DIR=".venv"
fi
if [ -z "$VENV_DIR" ]; then
    echo -e "${RED}  ERROR: Virtual environment not found.${NC}"
    echo "  Please run install.sh first."
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"

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

echo -e "  ${GREEN}🌐  Shogun is starting at http://localhost:8000${NC}"
echo "  📖  Your browser will open automatically."
echo ""
echo "  Press Ctrl+C to stop the server."
echo ""

# Start the server (blocking). A UI restart request leaves a marker that makes
# this launcher supervise a clean stop/start cycle.
export SHOGUN_BROWSER_URL=http://localhost:8000
export SHOGUN_LAUNCHER_MANAGED=true
while true; do
    set +e
    $PYTHON_CMD -m shogun
    SHOGUN_EXIT_CODE=$?
    set -e
    if [ -f ".states/restart-requested" ]; then
        rm -f ".states/restart-requested"
        echo "  Restart requested. Starting Shogun again..."
        sleep 2
        continue
    fi
    exit "$SHOGUN_EXIT_CODE"
done
