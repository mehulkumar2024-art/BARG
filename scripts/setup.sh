#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux ]]; then echo 'Use Ubuntu 24.04 for this setup script.' >&2; exit 1; fi
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip python3-bpfcc bpfcc-tools clang llvm linux-headers-"$(uname -r)" nodejs npm
python3 -m venv --system-site-packages .venv
mkdir -p data
.venv/bin/python -m pip install -r requirements.txt
if [[ $(node -p 'Number(process.versions.node.split(".")[0])') -lt 18 ]]; then echo 'Install Node 20 or 22 LTS before building.' >&2; exit 1; fi
(cd frontend && npm ci)
bash scripts/build.sh
echo 'Setup completed. Run bash scripts/check_environment.sh next.'
