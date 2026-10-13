#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m compileall -q barg
(cd frontend && npm run build)
echo 'Userspace build complete. BCC compiles and verifies telemetry.c when the Linux agent starts.'
