#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -e .
(cd frontend && npm install && npm run build)
echo "Install complete. Run ./start.sh or 'python -m shogun' to launch Shogun AgentFlow."
