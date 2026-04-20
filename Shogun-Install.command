#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  SHOGUN — One-Click Downloader & Installer (macOS / Linux)
#
#  This is a STANDALONE file. Download it, double-click it,
#  and Shogun will be installed automatically. No git required.
#  Prerequisites (Python, Node.js) will be installed for you.
#
#  macOS: Double-click this file, or: chmod +x Shogun-Install.command && ./Shogun-Install.command
# ═══════════════════════════════════════════════════════════════

set -e

# Colors
GOLD='\033[1;33m'
BLUE='\033[1;34m'
GREEN='\033[1;32m'
RED='\033[1;31m'
GRAY='\033[0;90m'
NC='\033[0m'
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
echo "  ║       AI Agent Framework — One-Click Installer           ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ── Configuration ──────────────────────────────────────────────
REPO="AlphaHorizon-AI/Shogun"
BRANCH="main"
INSTALL_DIR="$HOME/Shogun"
ZIP_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
ZIP_FILE="/tmp/shogun-download.zip"
EXTRACT_DIR="/tmp/shogun-extract"

# Detect OS
OS="$(uname -s)"
case "$OS" in
    Darwin*)  PLATFORM="macOS";;
    Linux*)   PLATFORM="Linux";;
    *)        PLATFORM="Unknown";;
esac
echo -e "  ${BLUE}Platform: ${BOLD}${PLATFORM}${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  Checking & installing prerequisites...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""



# ── Check Python ───────────────────────────────────────────────
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "  ${RED}❌  Python is not installed.${NC}"
    echo ""
    echo -e "  ${GRAY}Shogun requires Python 3.10+ to run.${NC}"
    echo -e "  ${GRAY}Please install it from https://www.python.org/downloads/ or via your package manager.${NC}"
    echo ""
    exit 1
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo -e "  ${GREEN}✅  $PY_VER${NC}"

# ── Check Node.js ──────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo -e "  ${RED}❌  Node.js is not installed.${NC}"
    echo ""
    echo -e "  ${GRAY}Shogun requires Node.js v18+ to build the interface.${NC}"
    echo -e "  ${GRAY}Please install it from https://nodejs.org/ or via your package manager.${NC}"
    echo ""
    exit 1
fi

NODE_VER=$(node --version 2>&1)
echo -e "  ${GREEN}✅  Node.js $NODE_VER${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  📥  Downloading Shogun from GitHub...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo "      $ZIP_URL"
echo ""

curl -fsSL -o "$ZIP_FILE" "$ZIP_URL"

if [ ! -f "$ZIP_FILE" ]; then
    echo -e "  ${RED}❌  Download failed. Check your internet connection.${NC}"
    read -p "  Press Enter to exit..." _
    exit 1
fi
echo -e "  ${GREEN}✅  Download complete.${NC}"
echo ""

# ── Extract ────────────────────────────────────────────────────
echo -e "  ${GOLD}📦  Extracting to $INSTALL_DIR...${NC}"

rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
unzip -qo "$ZIP_FILE" -d "$EXTRACT_DIR"

EXTRACTED="$EXTRACT_DIR/Shogun-$BRANCH"

if [ ! -d "$EXTRACTED" ]; then
    echo -e "  ${RED}❌  Extraction failed.${NC}"
    read -p "  Press Enter to exit..." _
    exit 1
fi

# Backup config if upgrading
if [ -f "$INSTALL_DIR/configs/setup.json" ]; then
    cp "$INSTALL_DIR/configs/setup.json" /tmp/shogun_setup_backup.json 2>/dev/null || true
fi

# Copy files (preserve data/ and venv/)
mkdir -p "$INSTALL_DIR"
if command -v rsync &>/dev/null; then
    rsync -a --exclude='data/' --exclude='venv/' --exclude='node_modules/' \
        "$EXTRACTED/" "$INSTALL_DIR/"
else
    cp -R "$EXTRACTED"/* "$INSTALL_DIR/"
fi

# Restore config backup
if [ -f /tmp/shogun_setup_backup.json ]; then
    mkdir -p "$INSTALL_DIR/configs"
    mv /tmp/shogun_setup_backup.json "$INSTALL_DIR/configs/setup.json"
fi

# Cleanup
rm -f "$ZIP_FILE"
rm -rf "$EXTRACT_DIR"

echo -e "  ${GREEN}✅  Extracted to $INSTALL_DIR${NC}"
echo ""

# ── Run installer ──────────────────────────────────────────────
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  🚀  Running Shogun installer...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

cd "$INSTALL_DIR"
chmod +x install.sh start.sh scripts/*.sh 2>/dev/null || true
bash install.sh
