#!/usr/bin/env bash
set -euo pipefail

# ===============================================================
#  GENSUI — One-Click Installer (macOS / Linux)
#  Central Command & Security Control Plane for Shogun
# ===============================================================

cd "$(dirname "$0")"

umask 077
GENSUI_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gensui-install.XXXXXX")"
cleanup_installer() {
    rm -rf -- "${GENSUI_TEMP_DIR:?}"
}
trap cleanup_installer EXIT
trap 'exit 130' HUP INT TERM

echo ""
echo "  +----------------------------------------------------------+"
echo "  :                                                          :"
echo "  :       GENSUI - Central Command for Shogun                :"
echo "  :       One-Click Installer                                :"
echo "  :                                                          :"
echo "  +----------------------------------------------------------+"
echo ""

# -- Step 1: Check Python -----------------------------------------
echo "[1/7] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "  ERROR: Python 3 is not installed."
    echo "  Install Python 3.10+ from https://python.org"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "  ERROR: Gensui requires Python 3.10 or newer."
    exit 1
fi
echo "       Found $PY_VER"

# -- Step 2: Check Node.js ----------------------------------------
echo "[2/7] Checking Node.js..."
if ! command -v node &>/dev/null; then
    echo "  ERROR: Node.js is not installed."
    echo "  Install Node.js 22.12 or newer, but below 25, from https://nodejs.org"
    exit 1
fi
NODE_VER=$(node --version 2>&1)
export GENSUI_NODE_VERSION="$NODE_VER"
if ! python3 -c "import os; p=tuple(map(int, os.environ['GENSUI_NODE_VERSION'].lstrip('v').split('.')[:2])); raise SystemExit(0 if (22, 12) <= p < (25, 0) else 1)"; then
    echo "  ERROR: Unsupported Node.js $NODE_VER. Gensui requires 22.12 or newer, but below 25."
    exit 1
fi
unset GENSUI_NODE_VERSION
echo "       Found Node.js $NODE_VER"

# -- Step 3: Create Python virtual environment --------------------
echo "[3/7] Creating Python virtual environment..."
if [ -d ".venv" ]; then
    echo "       Existing .venv found — reusing."
else
    python3 -m venv .venv
    echo "       Virtual environment created."
fi

# -- Step 4: Install Python dependencies --------------------------
echo "[4/7] Installing Gensui server dependencies..."
source .venv/bin/activate
pip install . --quiet --disable-pip-version-check
echo "       Server dependencies installed."

# -- Step 5: Build frontend ---------------------------------------
echo "[5/7] Building Gensui Admin UI..."
if [ -f "frontend/package.json" ]; then
    cd frontend
    if ! npm install --silent; then
        echo "  ERROR: Failed to install Gensui frontend dependencies."
        exit 1
    fi
    if ! npm run build --silent; then
        echo "  ERROR: Failed to build the Gensui Admin UI."
        exit 1
    fi
    cd ..
    echo "       Admin UI built."
else
    echo "       No frontend found — skipping."
fi

# -- Step 6: Create .env if not present ---------------------------
echo "[6/7] Configuring environment..."
if [ ! -f ".env" ]; then
    ADMIN_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    ENV_TEMP="$GENSUI_TEMP_DIR/.env"
    cp .env.example "$ENV_TEMP"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" "$ENV_TEMP"
    else
        sed -i "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" "$ENV_TEMP"
    fi
    install -m 600 "$ENV_TEMP" .env
    rm -f -- "$ENV_TEMP"
    unset ADMIN_SECRET ENV_TEMP
    echo "       .env created; JWT material will be generated in data/secrets."
else
    echo "       .env already exists — keeping existing config."
fi
chmod 600 .env

# -- Step 7: Start server -----------------------------------------
echo "[7/7] Starting Gensui..."
echo ""
echo "  +----------------------------------------------------------+"
echo "  :                                                          :"
echo "  :   Installation complete!                                 :"
echo "  :                                                          :"
echo "  :   Gensui is starting at http://localhost:8787            :"
echo "  :   API docs are disabled unless DEBUG=true                :"
echo "  :                                                          :"
echo "  :   Admin: admin@gensui.local                              :"
echo "  :   Password: stored in gensui/.env (mode 600)             :"
echo "  :                                                          :"
echo "  :   Press Ctrl+C to stop the server.                       :"
echo "  :                                                          :"
echo "  +----------------------------------------------------------+"
echo ""

# Open browser after delay (background)
(sleep 5 && python3 -c "import webbrowser; webbrowser.open('http://localhost:8787')") &

python3 -m gensui
