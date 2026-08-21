#!/usr/bin/env bash
set -euo pipefail

TELEMETRY_MODE="${SHOGUN_TELEMETRY:-ask}"
TELEMETRY_NOTICE="${SHOGUN_TELEMETRY_NOTICE_VERSION:-}"
SHOW_SETUP_LINK=0
for argument in "$@"; do
  case "$argument" in
    --telemetry=on) TELEMETRY_MODE=on ;;
    --telemetry=off) TELEMETRY_MODE=off ;;
    --accept-telemetry-notice=*) TELEMETRY_NOTICE="${argument#*=}" ;;
    --show-setup-link) SHOW_SETUP_LINK=1 ;;
    *) echo "ERROR: Unknown installer argument: $argument" >&2; exit 2 ;;
  esac
done
if [ ! -t 0 ] && [ "$TELEMETRY_MODE" = "ask" ]; then
  TELEMETRY_MODE=off
fi

REPO="AlphaHorizon-AI/Shogun"
BRANCH="main"
INSTALL_DIR="${SHOGUN_SERVER_DIR:-$HOME/shogun-server}"
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
if ! COMMIT_RESPONSE="$(curl --fail --location --silent --show-error \
  --header 'Accept: application/vnd.github+json' \
  --header 'User-Agent: Shogun-Server-Installer' \
  "https://api.github.com/repos/$REPO/commits/$BRANCH")"; then
  echo "ERROR: GitHub did not return the source commit." >&2
  exit 1
fi
SOURCE_COMMIT="$(printf '%s\n' "$COMMIT_RESPONSE" | sed -nE 's/^[[:space:]]*"sha":[[:space:]]*"([0-9a-fA-F]{40})",?[[:space:]]*$/\1/p' | sed -n '1p')"
if [[ ! "$SOURCE_COMMIT" =~ ^[0-9a-fA-F]{40}$ ]]; then
  echo "ERROR: GitHub did not return a verifiable source commit." >&2
  echo "Installation stopped instead of downloading a mutable branch archive." >&2
  exit 1
fi
SOURCE_COMMIT="$(printf '%s' "$SOURCE_COMMIT" | tr 'A-F' 'a-f')"
ARCHIVE_URL="https://github.com/$REPO/archive/$SOURCE_COMMIT.zip"
export VCS_REF="$SOURCE_COMMIT"
echo "      Source commit: $SOURCE_COMMIT"
curl --fail --location --silent --show-error "$ARCHIVE_URL" --output "$TEMP_ROOT/shogun.zip"
unzip -q "$TEMP_ROOT/shogun.zip" -d "$TEMP_ROOT/source"
SOURCE_DIR="$TEMP_ROOT/source/Shogun-$SOURCE_COMMIT"

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
  rm -f -- "$ENV_BACKUP"
  if [ -e "$ENV_BACKUP" ]; then
    echo "ERROR: The temporary server environment backup could not be removed." >&2
    exit 1
  fi
  ENV_BACKUP=""
fi

cd "$INSTALL_DIR"

if [ "$TELEMETRY_MODE" = "ask" ]; then
  echo ""
  echo "Help improve Shogun AFM (optional)"
  echo "Share version, platform family, Docker install type, Team Mode, a random"
  echo "installation ID, and one weekly active signal. No operational content is shared."
  echo "Privacy notice: https://www.alphahorizon.io/shogun/telemetry-privacy/"
  read -r -p "Share pseudonymous installation statistics? [y/N]: " TELEMETRY_CHOICE
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
  A2A_SECRET="$(openssl rand -hex 32)"
  if [ "$(uname -s)" = "Darwin" ]; then
    sed -i '' "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i '' "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-infrastructure-admin-token/$INFRASTRUCTURE_SECRET/" .env.server
    sed -i '' "s/change-me-to-an-independent-a2a-encryption-key/$A2A_SECRET/" .env.server
  else
    sed -i "s/change-me-postgres-password/$POSTGRES_SECRET/" .env.server
    sed -i "s/change-me-to-a-random-64-char-string/$APPLICATION_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-random-64-char-string/$VAULT_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-infrastructure-admin-token/$INFRASTRUCTURE_SECRET/" .env.server
    sed -i "s/change-me-to-an-independent-a2a-encryption-key/$A2A_SECRET/" .env.server
  fi
  chmod 600 .env.server
  unset POSTGRES_SECRET APPLICATION_SECRET VAULT_SECRET INFRASTRUCTURE_SECRET A2A_SECRET
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
set_env_value VCS_REF "$SOURCE_COMMIT"

SERVER_PORT="$(sed -n 's/^SHOGUN_PORT=//p' .env.server | sed -n '1p' | tr -d '\r')"
SERVER_PORT="${SERVER_PORT:-8000}"
if [[ ! "$SERVER_PORT" =~ ^[0-9]+$ ]]; then
  echo "ERROR: SHOGUN_PORT must be an integer from 1 through 65535." >&2
  exit 1
fi
SERVER_PORT=$((10#$SERVER_PORT))
if (( SERVER_PORT < 1 || SERVER_PORT > 65535 )); then
  echo "ERROR: SHOGUN_PORT must be an integer from 1 through 65535." >&2
  exit 1
fi
SETUP_ORIGIN="http://127.0.0.1:$SERVER_PORT"
HEALTH_URL="$SETUP_ORIGIN/api/v1/health"

echo "[4/5] Building and starting Shogun Server..."
docker compose --env-file .env.server -f docker-compose.server.yml up -d --build

echo "[5/5] Waiting for The Tenshu..."
for attempt in $(seq 1 90); do
  if curl --fail --silent "$HEALTH_URL" >/dev/null 2>&1; then
    echo ""
    echo "Shogun Server is ready at $SETUP_ORIGIN."
    echo "Team members should connect through Telegram or Microsoft Teams."
    echo ""
    if { [ -t 1 ] && [ -z "${CI:-}" ]; } || [ "$SHOW_SETUP_LINK" = "1" ]; then
      if ! SETUP_URL="$(docker compose --env-file .env.server -f docker-compose.server.yml \
        exec -T shogun python -m shogun.setup_link --origin "$SETUP_ORIGIN")"; then
        echo "ERROR: Shogun started, but a secure Primary Admin setup link could not be created." >&2
        exit 1
      fi
      echo "Private Primary Admin bootstrap link (treat the fragment as a credential):"
      printf '%s\n' "$SETUP_URL"
      echo "The browser removes the fragment before the first API request."
      unset SETUP_URL
    else
      echo "The credential-bearing setup link was withheld because output is redirected."
      echo "From a private operator terminal in '$INSTALL_DIR', run:"
      echo "docker compose --env-file .env.server -f docker-compose.server.yml exec -T shogun python -m shogun.setup_link --origin $SETUP_ORIGIN"
    fi
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
