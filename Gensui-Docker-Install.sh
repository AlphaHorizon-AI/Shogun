#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  GENSUI — One-Click Docker Downloader & Installer (macOS / Linux)
#
#  This is a STANDALONE file. Download it, run it,
#  and Gensui will be deployed via Docker automatically.
#  Prerequisites: Docker and Docker Compose (v2)
#
#  Usage: bash Gensui-Docker-Install.sh
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
echo "  ║     Gensui Server — One-Click Docker Installer           ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# ── Configuration ──────────────────────────────────────────────
REPO="AlphaHorizon-AI/Shogun"
BRANCH="main"
INSTALL_DIR="$HOME/gensui-server"
ZIP_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
ZIP_FILE="/tmp/gensui-docker-download.zip"
EXTRACT_DIR="/tmp/gensui-docker-extract"

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
echo -e "  ${GOLD}  [1/6] Checking prerequisites...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

if ! command -v docker &>/dev/null; then
    echo -e "  ${RED}❌  Docker is not installed.${NC}"
    echo ""
    echo -e "  ${GRAY}Please install Docker and Docker Compose to continue.${NC}"
    echo -e "  ${GRAY}See: https://docs.docker.com/get-docker/${NC}"
    echo ""
    exit 1
fi
DOCKER_VER=$(docker --version)
echo -e "  ${GREEN}✅  $DOCKER_VER${NC}"

if ! docker compose version &>/dev/null; then
    echo -e "  ${RED}❌  Docker Compose (v2 plugin) is not installed.${NC}"
    echo ""
    echo -e "  ${GRAY}Please install Docker Compose plugin.${NC}"
    echo -e "  ${GRAY}See: https://docs.docker.com/compose/install/${NC}"
    echo ""
    exit 1
fi
COMPOSE_VER=$(docker compose version)
echo -e "  ${GREEN}✅  $COMPOSE_VER${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  [2/6] Downloading Gensui from GitHub...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""
echo "      $ZIP_URL"
echo ""

curl -fsSL -o "$ZIP_FILE" "$ZIP_URL"

if [ ! -f "$ZIP_FILE" ]; then
    echo -e "  ${RED}❌  Download failed. Check your internet connection.${NC}"
    exit 1
fi
echo -e "  ${GREEN}✅  Download complete.${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  [3/6] Extracting to $INSTALL_DIR...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

rm -rf "$EXTRACT_DIR"
mkdir -p "$EXTRACT_DIR"
unzip -qo "$ZIP_FILE" -d "$EXTRACT_DIR"

EXTRACTED="$EXTRACT_DIR/Shogun-$BRANCH/gensui"

if [ ! -d "$EXTRACTED" ]; then
    echo -e "  ${RED}❌  Extraction failed.${NC}"
    exit 1
fi

# Backup config if upgrading
if [ -f "$INSTALL_DIR/.env" ]; then
    cp "$INSTALL_DIR/.env" /tmp/gensui_docker_setup_backup.env 2>/dev/null || true
fi

# Copy files (preserve data/ and certs/)
mkdir -p "$INSTALL_DIR"
if command -v rsync &>/dev/null; then
    rsync -a --exclude='data/' --exclude='certs/' \
        "$EXTRACTED/" "$INSTALL_DIR/"
else
    cp -R "$EXTRACTED"/* "$INSTALL_DIR/"
fi

# Restore config backup
if [ -f /tmp/gensui_docker_setup_backup.env ]; then
    mv /tmp/gensui_docker_setup_backup.env "$INSTALL_DIR/.env"
fi

# Cleanup
rm -f "$ZIP_FILE"
rm -rf "$EXTRACT_DIR"

echo -e "  ${GREEN}✅  Extracted to $INSTALL_DIR${NC}"
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  [4/6] Configuring environment...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

cd "$INSTALL_DIR"

if [ ! -f ".env" ]; then
    cp .env.example .env
    
    # Generate random JWT secret
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '\n' | tr -d '=' | tr -d '+' | tr -d '/')
    ADMIN_SECRET=$(openssl rand -base64 36 | tr -d '\n' | tr -d '=' | tr -d '+' | tr -d '/')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-to-a-random-64-char-string/$JWT_SECRET/" .env
        sed -i '' "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" .env
    else
        sed -i "s/change-me-to-a-random-64-char-string/$JWT_SECRET/" .env
        sed -i "s/change-me-to-a-random-admin-password/$ADMIN_SECRET/" .env
    fi
    echo -e "  ${GREEN}✅  .env created with secure random JWT and admin secrets.${NC}"
    echo -e "  ${GRAY}The generated admin password is stored in $INSTALL_DIR/.env (mode 600).${NC}"
    chmod 600 .env
else
    echo -e "  ${GREEN}✅  .env already exists — keeping existing config.${NC}"
fi
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  [5/6] TLS Setup (HTTPS)...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

USE_TLS=false
PROFILE="default"

echo "Do you want to enable HTTPS with Nginx? (y/n)"
read -r -p "If no, Gensui will run on HTTP port 8787. [y/N]: " ENABLE_HTTPS

if [[ "$ENABLE_HTTPS" =~ ^[Yy]$ ]]; then
    USE_TLS=true
    PROFILE="server"
    mkdir -p certs
    
    if [ ! -f "certs/gensui.crt" ] || [ ! -f "certs/gensui.key" ]; then
        echo ""
        echo "No TLS certificates found in ./certs/"
        echo "Would you like to generate a self-signed certificate now? (y/n)"
        read -r -p "Note: Self-signed certs will cause browser warnings. [Y/n]: " GEN_CERT
        
        if [[ ! "$GEN_CERT" =~ ^[Nn]$ ]]; then
            echo -e "  ${GRAY}Generating self-signed certificate...${NC}"
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout certs/gensui.key -out certs/gensui.crt \
                -subj "/C=US/ST=State/L=City/O=Shogun/CN=localhost" &>/dev/null
            echo -e "  ${GREEN}✅  Generated self-signed certs in ./certs/${NC}"
        else
            echo -e "  ${GOLD}⚠️  Please place 'gensui.crt' and 'gensui.key' in $INSTALL_DIR/certs/ before continuing.${NC}"
            read -r -p "Press Enter when ready..." _
        fi
    else
         echo -e "  ${GREEN}✅  TLS certificates found in ./certs/${NC}"
    fi
else
    echo -e "  ${GRAY}HTTPS setup skipped. Proceeding with basic HTTP setup.${NC}"
fi
echo ""

# ══════════════════════════════════════════════════════════════
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo -e "  ${GOLD}  [6/6] Launching Gensui with Docker Compose...${NC}"
echo -e "  ${GOLD}══════════════════════════════════════════════════${NC}"
echo ""

if [ "$USE_TLS" = true ]; then
    echo -e "  ${GRAY}Running: docker compose --profile server up -d${NC}"
    docker compose --profile server up -d
else
    echo -e "  ${GRAY}Running: docker compose up -d${NC}"
    docker compose up -d
fi

echo ""
echo -e "${GREEN}  ╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   ✅ Docker deployment complete!                         ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"

if [ "$USE_TLS" = true ]; then
    echo -e "${GREEN}  ║   Gensui is starting at https://localhost                ║${NC}"
else
    echo -e "${GREEN}  ║   Gensui is starting at http://localhost:8787            ║${NC}"
fi

echo -e "${GREEN}  ║   API docs at http(s)://localhost(:8787)/docs            ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   Admin: admin@gensui.local                              ║${NC}"
echo -e "${GREEN}  ║   Password: stored in the protected .env file            ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ║   To stop: docker compose down                           ║${NC}"
echo -e "${GREEN}  ║                                                          ║${NC}"
echo -e "${GREEN}  ╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
