#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — One-Click Installer (macOS / Linux)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail
umask 077

# Ensure we run from the script's own directory
cd "$(dirname "$0")"

TELEMETRY_MODE="${SHOGUN_TELEMETRY:-ask}"
TELEMETRY_NOTICE="${SHOGUN_TELEMETRY_NOTICE_VERSION:-}"
START_AFTER_INSTALL=true
RONIN_MODE=ask
for argument in "$@"; do
    case "$argument" in
        --telemetry=on) TELEMETRY_MODE="on" ;;
        --telemetry=off) TELEMETRY_MODE="off" ;;
        --accept-telemetry-notice=*) TELEMETRY_NOTICE="${argument#*=}" ;;
        --no-start) START_AFTER_INSTALL=false ;;
        --ronin=on) RONIN_MODE=on ;;
        --ronin=off) RONIN_MODE=off ;;
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
if [ "$PLATFORM" = "macOS" ]; then
    export PATH="$PATH:/opt/homebrew/bin:/usr/local/bin:/opt/homebrew/opt/node@22/bin:/usr/local/opt/node@22/bin"
fi
echo -e "${BLUE}  Detected platform: ${BOLD}${PLATFORM}${NC}"
echo ""

# ── Step 1: Check Python ───────────────────────────────────────
echo -e "${GOLD}[1/8]${NC} Checking Python..."

PYTHON_CMD="${PYTHON_CMD:-}"
if [ -z "$PYTHON_CMD" ]; then
    for candidate in python3.12 python3.13 python3.11 python3.10 python3 python; do
        if command -v "$candidate" &>/dev/null && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            PYTHON_CMD="$candidate"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}  ERROR: Python is not installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  Install via: brew install python@3.12"
    else
        echo "  Install via: sudo apt install python3 python3-venv python3-pip"
    fi
    exit 1
fi
if ! "$PYTHON_CMD" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo -e "${RED}  ERROR: Python 3.10 or newer is required.${NC}"
    exit 1
fi

if [ "$PLATFORM" = "macOS" ]; then
    if ! "$PYTHON_CMD" -c 'import platform; raise SystemExit(0 if platform.machine() == "arm64" else 1)'; then
        echo "ERROR: Native macOS installation requires Apple Silicon and an arm64 Python."
        echo "Intel Macs cannot install the required PyTorch wheels. Use Shogun Server with Docker."
        echo "On Apple Silicon, reopen Terminal without Rosetta and install an arm64 Python."
        exit 1
    fi
    MACOS_VERSION="$(sw_vers -productVersion)"
    if [ "${MACOS_VERSION%%.*}" -lt 14 ]; then
        echo "ERROR: macOS 14 (Sonoma) or later is required by the Mado browser engine."
        exit 1
    fi
fi
PY_VER=$("$PYTHON_CMD" --version 2>&1)
echo -e "       Found ${GREEN}${PY_VER}${NC}"

# ── Step 2: Check Node.js ──────────────────────────────────────
echo -e "${GOLD}[2/8]${NC} Checking Node.js..."

if ! command -v node &>/dev/null; then
    echo -e "${RED}  ERROR: Node.js is not installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo "  Install via: brew install node@22"
    else
        echo "  Install via: sudo apt install nodejs npm"
        echo "  Or use nvm: https://github.com/nvm-sh/nvm"
    fi
    exit 1
fi
if ! node -e "const [major,minor]=process.versions.node.split('.').map(Number); process.exit((major>22||major===22&&minor>=12)&&major<25?0:1)"; then
    echo -e "${RED}  ERROR: Node.js 22.12 or newer, but lower than 25, is required.${NC}"
    exit 1
fi

NODE_VER=$(node --version 2>&1)
echo -e "       Found ${GREEN}Node.js ${NODE_VER}${NC}"

# ── Step 3: Create Python virtual environment ──────────────────
echo -e "${GOLD}[3/8]${NC} Creating Python virtual environment..."

if [ ! -d "venv" ]; then
    "$PYTHON_CMD" -m venv venv
    echo "       Virtual environment created."
else
    echo "       Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate
# Always use this environment, including when PYTHON_CMD was an absolute path.
PYTHON_CMD="$(pwd)/venv/bin/python"
if ! "$PYTHON_CMD" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "ERROR: Existing venv is unusable. Move it aside and run install.sh again."
    exit 1
fi
if [ "$PLATFORM" = "macOS" ] && ! "$PYTHON_CMD" -c 'import platform; raise SystemExit(0 if platform.machine() == "arm64" else 1)'; then
    echo "ERROR: Existing venv is not arm64. Move it aside and rerun with a native arm64 Python."
    exit 1
fi

# ── Step 4: Install Python dependencies ────────────────────────
echo -e "${GOLD}[4/8]${NC} Installing Python dependencies..."
"$PYTHON_CMD" -m pip install ".[office]" --disable-pip-version-check
echo -e "       ${GREEN}Python dependencies installed.${NC}"

# Create/repair .env atomically before any application command imports settings.
# The helper never prints secret values; the installer also suppresses its status.
"$PYTHON_CMD" -m shogun.environment_bootstrap --root "$(pwd)" >/dev/null
chmod 600 .env
if ! "$PYTHON_CMD" -c "import stat; from pathlib import Path; p=Path('.env'); raise SystemExit(0 if p.is_file() and stat.S_IMODE(p.stat().st_mode) == 0o600 else 1)"; then
    echo -e "${RED}  ERROR: Could not protect the local environment file.${NC}"
    exit 1
fi
echo -e "       ${GREEN}Protected local administrator credential created.${NC}"

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
    TELEMETRY_CHOICE=""
    read -r -p "  Share pseudonymous installation statistics? [y/N]: " TELEMETRY_CHOICE || true
    if [[ "$TELEMETRY_CHOICE" =~ ^[Yy]$ ]]; then
        TELEMETRY_MODE="on"
        TELEMETRY_NOTICE="1.0"
    else
        TELEMETRY_MODE="off"
    fi
fi
if [ "$TELEMETRY_MODE" = "on" ] && [ "$TELEMETRY_NOTICE" = "1.0" ]; then
    "$PYTHON_CMD" -m shogun.telemetry.cli enable --notice-version 1.0
    echo -e "       ${GREEN}Optional installation telemetry enabled.${NC}"
elif [ "$TELEMETRY_MODE" = "on" ]; then
    echo -e "       ${RED}Telemetry remains disabled: notice version 1.0 was not explicitly accepted.${NC}"
    "$PYTHON_CMD" -m shogun.telemetry.cli disable
else
    "$PYTHON_CMD" -m shogun.telemetry.cli disable
    echo "       Optional installation telemetry remains disabled."
fi

# Install Mado browser engine (Playwright Chromium)
echo "       Installing Mado browser engine (Chromium)..."
"$PYTHON_CMD" -m playwright install chromium --with-deps
echo -e "       ${GREEN}Mado browser engine ready.${NC}"

# ── Step 4c: Ronin desktop control (optional) ──────────────────
echo ""
echo -e "${GOLD}  Optional: Enable desktop control (Ronin)?${NC}"
echo "  This allows the AI to control your mouse, keyboard, and take screenshots."
echo ""
INSTALL_RONIN=N
if [ "$RONIN_MODE" = "on" ]; then
    INSTALL_RONIN=y
elif [ "$RONIN_MODE" = "ask" ] && [ -t 0 ]; then
    read -r -p "  Install Ronin dependencies? [y/N]: " INSTALL_RONIN || true
fi

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
    "$PYTHON_CMD" -m pip install ".[ronin]" --disable-pip-version-check
    echo -e "       ${GREEN}Ronin desktop dependencies installed.${NC}"
    if [ "$PLATFORM" = "macOS" ]; then
        echo ""
        echo -e "       ${GOLD}⚠ macOS: You must grant Accessibility permissions to your terminal app.${NC}"
        echo "         Go to: System Settings → Privacy & Security → Accessibility"
        echo "         Add your terminal app (Terminal.app, iTerm2, VS Code, etc.)"
        echo "         Also enable Screen Recording for screenshots; macOS may request Input Monitoring."
        echo ""
    fi
else
    echo "       Skipping Ronin. You can enable it later in the Setup Wizard or Shogun Profile."
fi

# ── Step 5: Bootstrap database ─────────────────────────────────
echo -e "${GOLD}[5/8]${NC} Bootstrapping database..."
"$PYTHON_CMD" -c "import asyncio; from shogun.bootstrap import bootstrap; asyncio.run(bootstrap())"
echo -e "       ${GREEN}Database ready.${NC}"

# ── Step 6: Install and build frontend ─────────────────────────
echo -e "${GOLD}[6/8]${NC} Building frontend..."
(
    cd frontend
    npm ci --no-audit --no-fund
    npm run build
)
echo -e "       ${GREEN}Frontend built.${NC}"

# ── Step 7: Create desktop shortcut ────────────────────────────
echo -e "${GOLD}[7/8]${NC} Creating desktop shortcut..."
chmod +x start.sh
chmod +x scripts/create_shortcut_mac.sh
bash scripts/create_shortcut_mac.sh

if [ "$START_AFTER_INSTALL" = false ]; then
    echo "Installation complete. Launch Shogun with: bash start.sh"
    exit 0
fi

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

# The Python launcher adds the URL-encoded credential after '#'. The frontend
# consumes and scrubs that fragment before its first API request.
export SHOGUN_BROWSER_URL=http://localhost:8000/setup
exec bash start.sh
