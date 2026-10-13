#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $EUID != 0 ]]; then echo 'Run with sudo inside the Ubuntu VM.' >&2; exit 1; fi
ROOT=/sys/fs/cgroup/barg-lab
if [[ ! -d "$ROOT" ]]; then echo 'No BARG cgroup exists.'; exit 0; fi
for group in worker competitor; do
  if [[ -n "$(cat "$ROOT/$group/cgroup.procs")" ]]; then echo 'Managed processes are still running. Stop the workload and agent first.' >&2; exit 1; fi
done
.venv/bin/python -m barg.agent --root "$ROOT" --groups worker competitor --restore
rmdir "$ROOT/worker"
rmdir "$ROOT/competitor"
rmdir "$ROOT"
rm -f /run/barg/authorized-root
echo 'Original values restored; empty sandbox removed.'
