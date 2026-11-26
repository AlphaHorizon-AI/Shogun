#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
  PYTHON_EXE=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PYTHON_EXE="venv/bin/python"
else
  PYTHON_EXE="python3"
fi

export SHOGUN_LAUNCHER_MANAGED=true
while true; do
  set +e
  "$PYTHON_EXE" -m shogun "$@"
  code=$?
  set -e
  if [ -f ".states/restart-requested" ]; then
    rm -f ".states/restart-requested"
    sleep 2
    continue
  fi
  if [ -f ".states/shutdown-requested" ]; then
    rm -f ".states/shutdown-requested"
    exit 0
  fi
  exit "$code"
done
