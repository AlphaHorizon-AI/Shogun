#!/usr/bin/env sh
set -eu

umask 077

case "${SECRET_KEY:-}" in
  ""|change-me-*)
    echo "ERROR: SECRET_KEY must be set to a unique random value." >&2
    exit 1
    ;;
esac

case "${VAULT_ENCRYPTION_KEY:-}" in
  ""|change-me-*)
    echo "ERROR: VAULT_ENCRYPTION_KEY must be set to a unique random value." >&2
    exit 1
    ;;
esac

mkdir -p /app/data /app/vault /app/logs /app/configs /app/tmp

if [ "${DEPLOYMENT_MODE:-}" != "server" ]; then
  echo "ERROR: The server container requires DEPLOYMENT_MODE=server." >&2
  exit 1
fi

exec "$@"
