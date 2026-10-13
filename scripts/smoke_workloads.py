"""Run four one-second bounded userspace checks, independent of Linux governance."""
import json
import platform
from pathlib import Path
from barg.workload import run


if __name__ == '__main__':
    results = [run(kind, 1, 8, 'data/smoke-workloads') for kind in ('cpu', 'memory', 'io', 'anomaly')]
    directory = Path('results/userspace-smoke')
    directory.mkdir(parents=True, exist_ok=True)
    payload = {'platform': platform.platform(), 'scope': 'Bounded userspace workload smoke test; no eBPF or cgroup measurement', 'results': results}
    (directory / 'results.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
