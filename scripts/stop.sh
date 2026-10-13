#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f data/backend.pid ]]; then echo 'No backend PID recorded. Use Ctrl+C for manually launched processes.'; exit 0; fi
backend_pid=$(cat data/backend.pid)
if [[ ! "$backend_pid" =~ ^[0-9]+$ ]]; then echo 'Invalid PID record.' >&2; exit 1; fi
if [[ ! -r /proc/$backend_pid/cmdline ]]; then echo 'Recorded backend is already stopped.'; exit 0; fi
command_line=$(tr '\0' ' ' < "/proc/$backend_pid/cmdline")
if [[ "$command_line" != *'uvicorn barg.backend:app'* || "$(readlink -f "/proc/$backend_pid/cwd")" != "$PWD" ]]; then
  echo 'PID identity does not match this project backend; refusing to signal it.' >&2; exit 1
fi
kill -TERM "$backend_pid"
echo 'Backend stop requested. Stop the Linux agent with Ctrl+C to restore live controls.'
