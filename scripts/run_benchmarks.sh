#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $EUID != 0 ]]; then echo 'Run with sudo from an ordinary user inside your Ubuntu VM.' >&2; exit 1; fi
exec .venv/bin/python -m barg.evaluate --linux --output results/linux "$@"
