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

set -euo pipefail

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
TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/shogun-install.XXXXXXXX")"
ZIP_FILE="$TEMP_ROOT/shogun-download.zip"
EXTRACT_DIR="$TEMP_ROOT/extract"
SETUP_BACKUP="$TEMP_ROOT/setup.json"

cleanup() {
    rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT
umask 077

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
if ! "$PYTHON_CMD" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo -e "  ${RED}❌  Python 3.10 or newer is required.${NC}"
    exit 1
fi

PY_VER=$($PYTHON_CMD --version 2>&1)
echo -e "  ${GREEN}✅  $PY_VER${NC}"

# ── Check Node.js ──────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo -e "  ${RED}❌  Node.js is not installed.${NC}"
    echo ""
    echo -e "  ${GRAY}Shogun requires Node.js 22.12+ (but lower than 25) to build the interface.${NC}"
    echo -e "  ${GRAY}Please install it from https://nodejs.org/ or via your package manager.${NC}"
    echo ""
    exit 1
fi
if ! node -e "const [major,minor]=process.versions.node.split('.').map(Number); process.exit((major>22||major===22&&minor>=12)&&major<25?0:1)"; then
    echo -e "  ${RED}❌  Node.js 22.12 or newer, but lower than 25, is required.${NC}"
    exit 1
fi

NODE_VER=$(node --version 2>&1)
echo -e "  ${GREEN}✅  Node.js $NODE_VER${NC}"
echo ""

# Resolve first, then download that immutable commit. This prevents main from
# advancing between archive selection and provenance recording.
if ! COMMIT_RESPONSE="$(curl -fsSL \
    -H 'Accept: application/vnd.github+json' \
    -H 'User-Agent: Shogun-Installer' \
    "https://api.github.com/repos/$REPO/commits/$BRANCH")"; then
    echo -e "  ${RED}❌  GitHub did not return the source commit.${NC}"
    exit 1
fi
SOURCE_COMMIT="$(printf '%s\n' "$COMMIT_RESPONSE" | sed -nE 's/^[[:space:]]*"sha":[[:space:]]*"([0-9a-fA-F]{40})",?[[:space:]]*$/\1/p' | sed -n '1p')"
if [[ ! "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
    echo -e "  ${RED}❌  GitHub did not return a verifiable source commit.${NC}"
    echo -e "  ${GRAY}Installation stopped instead of downloading a mutable branch archive.${NC}"
    exit 1
fi
SOURCE_COMMIT="$(printf '%s' "$SOURCE_COMMIT" | tr 'A-F' 'a-f')"
ZIP_URL="https://github.com/$REPO/archive/$SOURCE_COMMIT.zip"

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  📥  Downloading Shogun from GitHub...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo "      Source commit: $SOURCE_COMMIT"
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

mkdir -p "$EXTRACT_DIR"
unzip -qo "$ZIP_FILE" -d "$EXTRACT_DIR"

EXTRACTED="$EXTRACT_DIR/Shogun-$SOURCE_COMMIT"

if [ ! -f "$EXTRACTED/version.json" ]; then
    echo -e "  ${RED}❌  Extraction failed.${NC}"
    read -p "  Press Enter to exit..." _
    exit 1
fi

# Backup config if upgrading
if [ -f "$INSTALL_DIR/configs/setup.json" ]; then
    cp "$INSTALL_DIR/configs/setup.json" "$SETUP_BACKUP"
    chmod 600 "$SETUP_BACKUP"
fi

# Copy files (preserve data/ and venv/)
mkdir -p "$INSTALL_DIR"
if command -v rsync &>/dev/null; then
    rsync -a --exclude='/data/' --exclude='/venv/' --exclude='/.venv/' --exclude='/node_modules/' --exclude='/frontend/node_modules/' \
        "$EXTRACTED/" "$INSTALL_DIR/"
else
    cp -R "$EXTRACTED/." "$INSTALL_DIR/"
fi

# Restore config backup
if [ -f "$SETUP_BACKUP" ]; then
    mkdir -p "$INSTALL_DIR/configs"
    cp "$SETUP_BACKUP" "$INSTALL_DIR/configs/setup.json"
fi

if ! cmp -s "$EXTRACTED/version.json" "$INSTALL_DIR/version.json"; then
    echo -e "  ${RED}❌  Installation verification failed; release provenance was not recorded.${NC}"
    exit 1
fi

if "$PYTHON_CMD" "$INSTALL_DIR/scripts/write_release_metadata_evidence.py" \
    --root "$INSTALL_DIR" --git-sha "$SOURCE_COMMIT" >/dev/null 2>&1; then
    echo -e "  ${GREEN}✅  Release provenance recorded.${NC}"
else
    echo -e "  ${GOLD}⚠️  Release provenance could not be recorded.${NC}"
fi

cleanup
trap - EXIT

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
