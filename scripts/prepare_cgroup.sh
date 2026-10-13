#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID != 0 ]]; then echo 'Run with sudo inside the Ubuntu VM.' >&2; exit 1; fi
ROOT=/sys/fs/cgroup/barg-lab
if [[ ! -f /sys/fs/cgroup/cgroup.controllers ]]; then echo 'cgroups v2 is required.' >&2; exit 1; fi
if [[ -e "$ROOT" ]]; then echo 'barg-lab already exists. Inspect it and run cleanup before preparing a fresh sandbox.' >&2; exit 1; fi
for controller in cpu memory; do
  if ! grep -qw "$controller" /sys/fs/cgroup/cgroup.subtree_control; then
    echo "Root $controller controller is not enabled. Ask the VM administrator to enable delegation before running." >&2
    exit 1
  fi
done
install -d -m 700 /run/barg
mkdir "$ROOT"
printf '+cpu +memory' > "$ROOT/cgroup.subtree_control"
mkdir "$ROOT/worker"
mkdir "$ROOT/competitor"
printf '%s\n' "$ROOT" > /run/barg/authorized-root
chmod 600 /run/barg/authorized-root
echo "Authorized empty sandbox: $ROOT/worker. Only benchmark-launched processes will enter it."
