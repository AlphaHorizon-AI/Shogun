#!/usr/bin/env bash
set -euo pipefail

REPO="AlphaHorizon-AI/Shogun"
BRANCH="main"
INSTALL_DIR="${SHOGUN_SERVER_DIR:-$HOME/shogun-server}"
ARCHIVE_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip"
TEMP_ROOT="$(mktemp -d)"
ENV_BACKUP="$TEMP_ROOT/env.server.backup"

cleanup() {
  rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

echo ""
echo "Shogun Server mode installer"
echo "============================"
echo ""

for command_name in docker curl unzip openssl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "ERROR: '$command_name' is required." >&2
    exit 1
  fi
done

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose v2 is required." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is installed but the daemon is not running." >&2
  exit 1
fi

echo "[1/5] Downloading Shogun..."
curl --fail --location --silent --show-error "$ARCHIVE_URL" --output "$TEMP_ROOT/shogun.zip"
unzip -q "$TEMP_ROOT/shogun.zip" -d "$TEMP_ROOT/source"
SOURCE_DIR="$TEMP_ROOT/source/Shogun-$BRANCH"

if [ ! -f "$SOURCE_DIR/docker-compose.server.yml" ]; then
  echo "ERROR: The downloaded archive does not contain Server mode." >&2
  exit 1
fi

echo "[2/5] Installing files in $INSTALL_DIR..."
if [ -f "$INSTALL_DIR/.env.server" ]; then
  cp "$INSTALL_DIR/.env.server" "$ENV_BACKUP"
fi
mkdir -p "$INSTALL_DIR"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --delete --exclude='.env.server' "$SOURCE_DIR/" "$INSTALL_DIR/"
else
  cp -R "$SOURCE_DIR/." "$INSTALL_DIR/"
fi

if [ -f "$ENV_BACKUP" ]; then
  cp "$ENV_BACKUP" "$INSTALL_DIR/.env.server"
fi

cd "$INSTALL_DIR"

echo "[3/5] Configuring secrets..."
if [ ! -f .env.server ]; then
  cp .env.server.example .env.server
  POSTGRES_SECRET="$(openssl rand -hex 32)"
  APPLICATION_SECRET="$(openssl rand -hex 32)"
  VAULT_SECRET="$(openssl rand -hex 32)"
  if [ "$(uname -s)" = "Darwin" ]; then
    sed -i '' "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i '' "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
  else
    sed -i "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
  fi
  chmod 600 .env.server
else
  echo "      Existing .env.server retained."
fi

echo "[4/5] Building and starting Shogun Server..."
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build

echo "[5/5] Waiting for The Tenshu..."
for attempt in $(seq 1 90); do
  if curl --fail --silent http://127.0.0.1:8000/api/v1/health >/dev/null 2>&1; then
    echo ""
    echo "Shogun Server is ready: http://127.0.0.1:8000/setup"
    echo "Team members should connect through Telegram or Microsoft Teams."
    echo ""
    echo "Manage: cd '$INSTALL_DIR'"
    echo "Logs:   docker compose --env-file .env.server -f docker-compose.server.yml logs -f shogun"
    echo "Stop:   docker compose --env-file .env.server -f docker-compose.server.yml down"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Shogun did not become healthy in time." >&2
docker compose --env-file .env.server -f docker-compose.server.yml ps >&2
exit 1
