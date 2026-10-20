# Current implementation status — 20 October 2026

## Working locally

Real host process readings; distinct dashboard pages; live charts; timed observation recordings; persistent incident events; optional Windows workload priority supervisor. The supervisor is opt-in and targets only its directly launched process. See RESOURCE_RESPONSE.md for thresholds and limits.

Start on Windows:

```powershell
cd "C:\Users\Mehul\Desktop\os project"
powershell -File scripts/start.ps1 -Port 8080
```

Open http://127.0.0.1:8080/. To run the included real workload under the Windows supervisor, use a second terminal:

```powershell
.\.venv\Scripts\python.exe -m barg.guard -- .\.venv\Scripts\python.exe -m barg.workload --kind cpu --duration 60
```

The backend monitors real processes. The workload is an intentionally generated real test load, not fabricated telemetry. A single CPU worker may not reach the system-pressure threshold; no intervention is expected unless both thresholds are crossed.

## Evidence and limits

Full Windows regression suite on 20 October: 48 passed, 3 skipped. One Starlette/httpx deprecation warning remains. Frontend is typechecked during the production build. Windows priority lowering and restoration were previously exercised on a disposable child.

`python -m scripts.compare_windows` runs 18 randomized two-second userspace trials (CPU, memory and I/O; baseline and supervised; three repeats). Its output is results/windows-comparison/results.json. This measures short workload throughput under current host load. It does not establish Linux governance improvement, isolate machine-wide overhead or guarantee priority-relief activation. Raw measurements and guard reports stay local and are not published to the public repository.

### Measured userspace smoke comparison (20 October)

18 trials completed. Median throughput in operations/second:

| Workload | Baseline | Supervised |
|---|---:|---:|
| CPU | 207,503 | 215,263 |
| Memory | 1,866,403 | 1,934,693 |
| File I/O | 149.64 | 149.85 |

No priority interventions occurred. The two-second trials are shorter than the three-reading response confirmation window and are only a launch/throughput smoke comparison. Differences can reflect uncontrolled host load and run variance; they are not evidence that BARG improves performance. Longer controlled contention experiments remain required.

## Ubuntu acceptance remains pending

The development machine has only the Docker Desktop WSL distribution; no Ubuntu test host is available. Do not use Docker Desktop's internal distribution for cgroup experiments. Use an isolated Ubuntu 24.04 VM with a snapshot and matching kernel headers. Follow STEP_BY_STEP.md for setup, then:

```bash
bash scripts/check_environment.sh
bash scripts/run_tests.sh
sudo bash scripts/run_benchmarks.sh --repeats 3 --duration 40
```

Require successful real BCC attachment, bounded cgroup writes, restoration after interruption, and measurements for vanilla/monitoring/CPU/memory/full modes before claiming kernel validation. Inspect capability reports and raw trial logs; a skipped test or unavailable feature is not a pass.

## Deployment

GitHub Pages serves static files only. The disconnected screen explains how to start a backend instead of showing fabricated zero metrics. A public monitoring service needs a separate Ubuntu host and DNS access.

See ../deploy/README.md for the proposed HTTPS/authenticated deployment. Those templates are prepared, not deployed or validated on a real server. The older Word documents describe earlier iterations and are historical; use this status page and RESOURCE_RESPONSE.md for current behavior.
