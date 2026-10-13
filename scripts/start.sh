#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export BARG_MODE=${BARG_MODE:-demo}
mkdir -p data
if [[ -f data/backend.pid ]] && kill -0 "$(cat data/backend.pid)" 2>/dev/null; then
  echo 'A recorded backend is still running. Use scripts/stop.sh first.' >&2
  exit 1
fi
.venv/bin/python -m uvicorn barg.backend:app --host 127.0.0.1 --port 8000 &
backend_pid=$!
printf '%s\n' "$backend_pid" > data/backend.pid
finish() { kill -TERM "$backend_pid" 2>/dev/null || true; wait "$backend_pid" 2>/dev/null || true; rm -f data/backend.pid; }
trap finish EXIT
trap 'exit 0' INT TERM
wait "$backend_pid"
