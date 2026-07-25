#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — One-Click Installer (macOS / Linux)
# ═══════════════════════════════════════════════════════════════

set -e

# Ensure we run from the script's own directory
cd "$(dirname "$0")"

TELEMETRY_MODE="${SHOGUN_TELEMETRY:-ask}"
TELEMETRY_NOTICE="${SHOGUN_TELEMETRY_NOTICE_VERSION:-}"
for argument in "$@"; do
    case "$argument" in
        --telemetry=on) TELEMETRY_MODE="on" ;;
        --telemetry=off) TELEMETRY_MODE="off" ;;
        --accept-telemetry-notice=*) TELEMETRY_NOTICE="${argument#*=}" ;;
        *)
            echo "ERROR: Unknown installer argument: $argument" >&2
            exit 2
            ;;
    esac
done
if [ ! -t 0 ] && [ "$TELEMETRY_MODE" = "ask" ]; then
    TELEMETRY_MODE="off"
fi

# Colors
GOLD='\033[1;33m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

echo ""
echo -e "${GOLD}"
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║                                                          ║"
echo "  ║     ███████╗██╗  ██╗ ██████╗  ██████╗ ██╗   ██╗███╗   ██╗║"
echo "  ║     ██╔════╝██║  ██║██╔═══██╗██╔════╝ ██║   ██║████╗  ██║║"
echo "  ║     ███████╗███████║██║   ██║██║  ███╗██║   ██║██╔██╗ ██║║"
echo "  ║     ╚════██║██╔══██║██║   ██║██║   ██║██║   ██║██║╚██╗██║║"
echo "  ║     ███████║██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝██║ ╚████║║"
echo "  ║     ╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝║"
echo "  ║                                                          ║"
echo "  ║          AI Agent Framework — Installer v1.0             ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Darwin*)  PLATFORM="macOS";;
    Linux*)   PLATFORM="Linux";;
    *)        PLATFORM="Unknown";;
esac
echo -e "${BLUE}  Detected platform: ${BOLD}${PLATFORM}${NC}"
echo ""

# ── Step 1: Check Python ───────────────────────────────────────
echo -e "${GOLD}[1/8]${NC} Checking Python..."

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}  ERROR: Python is not installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  Install via: brew install python"
    else
        echo "  Install via: sudo apt install python3 python3-venv python3-pip"
    fi
    exit 1
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo -e "       Found ${GREEN}${PY_VER}${NC}"

# ── Step 2: Check Node.js ──────────────────────────────────────
echo -e "${GOLD}[2/8]${NC} Checking Node.js..."

if ! command -v node &>/dev/null; then
    echo -e "${RED}  ERROR: Node.js is not installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  Install via: brew install node"
    else
        echo "  Install via: sudo apt install nodejs npm"
        echo "  Or use nvm: https://github.com/nvm-sh/nvm"
    fi
    exit 1
fi

NODE_VER=$(node --version 2>&1)
echo -e "       Found ${GREEN}Node.js ${NODE_VER}${NC}"

# ── Step 3: Create Python virtual environment ──────────────────
echo -e "${GOLD}[3/8]${NC} Creating Python virtual environment..."

if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    echo "       Virtual environment created."
else
    echo "       Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# ── Step 4: Install Python dependencies ────────────────────────
echo -e "${GOLD}[4/8]${NC} Installing Python dependencies..."
pip install ".[office]" --quiet --disable-pip-version-check
echo -e "       ${GREEN}Python dependencies installed.${NC}"

# Optional installation telemetry — separate from licence acceptance and off by default.
if [ "$TELEMETRY_MODE" = "ask" ]; then
    echo ""
    echo -e "${GOLD}  Help improve Shogun AFM (optional)${NC}"
    echo "  Share: version, OS family, install type, operating mode, random installation ID,"
    echo "  and one weekly active-installation signal."
    echo "  Never share: prompts, responses, files, memory, messages, people, credentials,"
    echo "  local paths, hostnames, or hardware identifiers."
    echo "  Exact schema: docs/telemetry.md"
    echo "  Privacy notice: https://www.alphahorizon.io/shogun/telemetry-privacy/"
    read -r -p "  Share anonymous installation statistics? [y/N]: " TELEMETRY_CHOICE
    if [[ "$TELEMETRY_CHOICE" =~ ^[Yy]$ ]]; then
        TELEMETRY_MODE="on"
        TELEMETRY_NOTICE="1.0"
    else
        TELEMETRY_MODE="off"
    fi
fi
if [ "$TELEMETRY_MODE" = "on" ] && [ "$TELEMETRY_NOTICE" = "1.0" ]; then
    $PYTHON_CMD -m shogun.telemetry.cli enable --notice-version 1.0
    echo -e "       ${GREEN}Optional installation telemetry enabled.${NC}"
elif [ "$TELEMETRY_MODE" = "on" ]; then
    echo -e "       ${RED}Telemetry remains disabled: notice version 1.0 was not explicitly accepted.${NC}"
    $PYTHON_CMD -m shogun.telemetry.cli disable
else
    $PYTHON_CMD -m shogun.telemetry.cli disable
    echo "       Optional installation telemetry remains disabled."
fi

# Install Mado browser engine (Playwright Chromium)
echo "       Installing Mado browser engine (Chromium)..."
$PYTHON_CMD -m playwright install chromium --with-deps 2>/dev/null || true
echo -e "       ${GREEN}Mado browser engine ready.${NC}"

# ── Step 4c: Ronin desktop control (optional) ──────────────────
echo ""
echo -e "${GOLD}  Optional: Enable desktop control (Ronin)?${NC}"
echo "  This allows the AI to control your mouse, keyboard, and take screenshots."
echo ""
read -p "  Install Ronin dependencies? [y/N]: " INSTALL_RONIN

if [[ "$INSTALL_RONIN" =~ ^[Yy]$ ]]; then
    # OS-specific system packages
    if [ "$PLATFORM" = "Linux" ]; then
        echo "       Installing Linux X11 system dependencies for Ronin..."
        if command -v apt &>/dev/null; then
            sudo apt install -y xdotool python3-tk python3-dev 2>/dev/null || true
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y xdotool python3-tkinter python3-devel 2>/dev/null || true
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm xdotool tk 2>/dev/null || true
        fi
    fi
    pip install ".[ronin]" --quiet --disable-pip-version-check
    echo -e "       ${GREEN}Ronin desktop dependencies installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo ""
        echo -e "       ${GOLD}⚠ macOS: You must grant Accessibility permissions to your terminal app.${NC}"
        echo "         Go to: System Preferences → Privacy & Security → Accessibility"
        echo "         Add your terminal app (Terminal.app, iTerm2, VS Code, etc.)"
        echo ""
    fi
else
    echo "       Skipping Ronin. You can enable it later in the Setup Wizard or Shogun Profile."
fi

# ── Step 5: Bootstrap database ─────────────────────────────────
echo -e "${GOLD}[5/8]${NC} Bootstrapping database..."
$PYTHON_CMD -c "import asyncio; from shogun.bootstrap import bootstrap; asyncio.run(bootstrap())" 2>/dev/null || true
echo -e "       ${GREEN}Database ready.${NC}"

# ── Step 6: Install and build frontend ─────────────────────────
echo -e "${GOLD}[6/8]${NC} Building frontend..."
cd frontend
if ! npm install --silent 2>/dev/null; then
    echo -e "       ${RED}WARNING: npm install failed. The frontend may not work correctly.${NC}"
    echo "       Try running 'npm install' manually in the frontend folder."
    cd ..
else
    if ! npm run build --silent 2>/dev/null; then
        echo -e "       ${RED}WARNING: Frontend build failed. The UI may be outdated.${NC}"
        echo "       Try running 'npm run build' manually in the frontend folder."
        cd ..
    else
        cd ..
        echo -e "       ${GREEN}Frontend built.${NC}"
    fi
fi

# ── Step 7: Create desktop shortcut ────────────────────────────
echo -e "${GOLD}[7/8]${NC} Creating desktop shortcut..."
chmod +x start.sh
chmod +x scripts/create_shortcut_mac.sh
bash scripts/create_shortcut_mac.sh

# ── Step 8: Start ──────────────────────────────────────────────
echo -e "${GOLD}[8/8]${NC} Starting Shogun..."
echo ""
echo -e "${GREEN}  ╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   ✅ Installation complete!                              ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   Shogun is starting at http://localhost:8000/setup      ║${NC}"
echo -e "${GREEN}  ║   Your browser will open when the server is ready.      ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   A desktop shortcut has been created.                   ║${NC}"
echo -e "${GREEN}  ║   Use it to launch Shogun in the future.                ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   Press Ctrl+C to stop the server.                      ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Wait for backend to be ready, then open browser (background)
(
    for i in $(seq 1 90); do
        if curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/health 2>/dev/null | grep -q '^200$'; then
            if [ "$PLATFORM" = "macOS" ]; then
                open "http://localhost:8000/setup" 2>/dev/null || true
            else
                xdg-open "http://localhost:8000/setup" 2>/dev/null || true
            fi
            exit 0
        fi
        sleep 1
    done
    echo "  Warning: Server did not respond in time. Open http://localhost:8000/setup manually."
) &

# Start the server (blocking)
$PYTHON_CMD -m shogun
