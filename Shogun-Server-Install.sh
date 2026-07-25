#!/usr/bin/env bash
set -euo pipefail

TELEMETRY_MODE="${SHOGUN_TELEMETRY:-ask}"
TELEMETRY_NOTICE="${SHOGUN_TELEMETRY_NOTICE_VERSION:-}"
for argument in "$@"; do
  case "$argument" in
    --telemetry=on) TELEMETRY_MODE=on ;;
    --telemetry=off) TELEMETRY_MODE=off ;;
    --accept-telemetry-notice=*) TELEMETRY_NOTICE="${argument#*=}" ;;
    *) echo "ERROR: Unknown installer argument: $argument" >&2; exit 2 ;;
  esac
done
if [ ! -t 0 ] && [ "$TELEMETRY_MODE" = "ask" ]; then
  TELEMETRY_MODE=off
fi

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

if [ "$TELEMETRY_MODE" = "ask" ]; then
  echo ""
  echo "Help improve Shogun AFM (optional)"
  echo "Share version, platform family, Docker install type, Team Mode, a random"
  echo "installation ID, and one weekly active signal. No operational content is shared."
  echo "Privacy notice: https://www.alphahorizon.io/shogun/telemetry-privacy/"
  read -r -p "Share anonymous installation statistics? [y/N]: " TELEMETRY_CHOICE
  if [[ "$TELEMETRY_CHOICE" =~ ^[Yy]$ ]]; then
    TELEMETRY_MODE=on
    TELEMETRY_NOTICE=1.0
  else
    TELEMETRY_MODE=off
  fi
fi
if [ "$TELEMETRY_MODE" = "on" ] && [ "$TELEMETRY_NOTICE" != "1.0" ]; then
  echo "Telemetry remains disabled: notice version 1.0 was not explicitly accepted."
  TELEMETRY_MODE=off
  TELEMETRY_NOTICE=
fi

echo "[3/5] Configuring secrets..."
if [ ! -f .env.server ]; then
  cp .env.server.example .env.server
  POSTGRES_SECRET="$(openssl rand -hex 32)"
  APPLICATION_SECRET="$(openssl rand -hex 32)"
  VAULT_SECRET="$(openssl rand -hex 32)"
  INFRASTRUCTURE_SECRET="$(openssl rand -hex 32)"
  if [ "$(uname -s)" = "Darwin" ]; then
    sed -i '' "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i '' "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-infrastructure-admin-token/$INFRASTRUCTURE_SECRET/" .env.server
  else
    sed -i "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-infrastructure-admin-token/$INFRASTRUCTURE_SECRET/" .env.server
  fi
  chmod 600 .env.server
else
  echo "      Existing .env.server retained."
fi

set_env_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env.server; then
    if [ "$(uname -s)" = "Darwin" ]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" .env.server
    else
      sed -i "s|^${key}=.*|${key}=${value}|" .env.server
    fi
  else
    printf '%s=%s\n' "$key" "$value" >> .env.server
  fi
}
set_env_value SHOGUN_TELEMETRY "$TELEMETRY_MODE"
set_env_value SHOGUN_TELEMETRY_NOTICE_VERSION "$TELEMETRY_NOTICE"

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
