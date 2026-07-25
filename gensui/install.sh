#!/usr/bin/env bash
set -euo pipefail

# ===============================================================
#  GENSUI — One-Click Installer (macOS / Linux)
#  Central Command & Security Control Plane for Shogun
# ===============================================================

cd "$(dirname "$0")"

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
echo "       Found $PY_VER"

# -- Step 2: Check Node.js ----------------------------------------
echo "[2/7] Checking Node.js..."
if ! command -v node &>/dev/null; then
    echo "  ERROR: Node.js is not installed."
    echo "  Install Node.js 18+ from https://nodejs.org"
    exit 1
fi
NODE_VER=$(node --version 2>&1)
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
    npm install --silent 2>/dev/null
    npm run build --silent 2>/dev/null
    cd ..
    echo "       Admin UI built."
else
    echo "       No frontend found — skipping."
fi

# -- Step 6: Create .env if not present ---------------------------
echo "[6/7] Configuring environment..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
    ADMIN_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-to-a-random-64-char-string/$JWT_SECRET/" .env
        sed -i '' "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" .env
    else
        sed -i "s/change-me-to-a-random-64-char-string/$JWT_SECRET/" .env
        sed -i "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" .env
    fi
    chmod 600 .env
    echo "       .env created with random secrets."
else
    echo "       .env already exists — keeping existing config."
fi

# -- Step 7: Start server -----------------------------------------
echo "[7/7] Starting Gensui..."
echo ""
echo "  +----------------------------------------------------------+"
echo "  :                                                          :"
echo "  :   Installation complete!                                 :"
echo "  :                                                          :"
echo "  :   Gensui is starting at http://localhost:8787            :"
echo "  :   API docs at http://localhost:8787/docs                 :"
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
