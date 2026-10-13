#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then echo 'Use Ubuntu 24.04 for this setup script.' >&2; exit 1; fi
if ! command -v node >/dev/null || [[ $(node -p 'Number(process.versions.node.split(".")[0])') -lt 20 ]]; then
  echo 'Install Node.js 22 or 24 with npm, then rerun. The dashboard requires Node >=20. See https://nodejs.org/en/download' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-bpfcc bpfcc-tools clang llvm linux-headers-"$(uname -r)"
python3 -m venv --system-site-packages .venv
mkdir -p data
.venv/bin/python -m pip install -r requirements.txt
(cd frontend && npm ci)
bash scripts/build.sh
echo 'Setup completed. Run bash scripts/check_environment.sh next.'
