#!/usr/bin/env sh
set -eu

umask 077

case "${GENSUI_JWT_SECRET:-}" in
  ""|change-me-*)
    echo "ERROR: GENSUI_JWT_SECRET must be set to a unique random value." >&2
    exit 1
    ;;
esac

case "${GENSUI_ADMIN_PASSWORD:-}" in
  ""|changeme|change-me-*)
    echo "ERROR: GENSUI_ADMIN_PASSWORD must be changed before Gensui starts." >&2
    exit 1
    ;;
esac

mkdir -p /app/data /app/logs

exec "$@"
