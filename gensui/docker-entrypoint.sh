#!/usr/bin/env sh
set -eu

umask 077

case "${GENSUI_ADMIN_PASSWORD:-}" in
  ""|changeme|change-me-*)
    echo "ERROR: GENSUI_ADMIN_PASSWORD must be changed before Gensui starts." >&2
    exit 1
    ;;
esac

mkdir -p /app/data/secrets /app/logs

exec "$@"
