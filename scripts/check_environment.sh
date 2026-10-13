#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON=${BARG_PYTHON:-.venv/bin/python}
"$PYTHON" -c 'import json; from barg.collector import capabilities; print(json.dumps(capabilities(),indent=2))'
"$PYTHON" -c 'import fastapi, uvicorn; print("Python application dependencies: OK")'
node --version
command -v clang || true
if [[ -f /sys/fs/cgroup/cgroup.controllers ]]; then cat /sys/fs/cgroup/cgroup.controllers; fi
echo 'A false capability is unavailable, not a successful kernel check. Use --require-ebpf for strict live verification.'
