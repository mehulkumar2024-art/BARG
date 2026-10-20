# BARG — Behavior-Aware Resource Governance

## Responsiveness experiment lab

Compare baseline, monitoring-only and adaptive Windows scheduling using two owned workers on one logical CPU. The Experiments page shows measured latency, throughput, variability and interventions. See [lab guide](docs/RESPONSIVENESS_LAB.md) for the command, methodology and limits.

## Current default is real system monitoring

**Current release status and instructions:** [CURRENT_STATUS.md](docs/CURRENT_STATUS.md). Includes live incident detection, Windows guarded workloads, deployment handoff and remaining Ubuntu acceptance checks. Older demo instructions and Word documents below are historical.

Run `powershell -File scripts/start.ps1 -Port 8080` and open http://127.0.0.1:8080/.
The default backend now reads actual local processes with psutil: process names, PIDs, CPU time deltas, RSS, thread counts and available I/O counters. Search and sort the live process table. Protected or exited processes are skipped. New processes display a dash for rates until the second reading.

This mode is read-only. It does not fabricate CPU bursts, syscall sequences, anomaly scores or control decisions. Kernel tracing and cgroup controls require the separate Ubuntu agent. Resource incidents now run in system mode; optional Windows priority response runs in a separate guard supervisor (see docs/RESOURCE_RESPONSE.md). System readings are stored separately in `data/system.sqlite3`; exports do not mix in demo records. Install updated dependencies with `pip install -r requirements.txt` in the project virtualenv. Stop an older server and restart after updating.

The historical demo instructions below describe the optional `BARG_MODE=demo` mode, not the current default. Use `BARG_MODE=live` for the existing Ubuntu agent bridge.

**An eBPF-driven closed-loop research prototype for adaptive CPU shares, memory protection, and behavioral anomaly detection.**

Develop the dashboard, algorithms, simulator, and tests on Windows. Validate real tracing and resource control in an isolated Ubuntu 24.04 VM. This implementation does not replace the Linux scheduler or page-replacement algorithm.

**Start here:** [beginner step-by-step guide](docs/STEP_BY_STEP.md) explains the project, browser demo, every dashboard view, Ubuntu implementation, experiments and troubleshooting.

## What runs

- React + TypeScript + Tailwind dashboard with eight views, live WebSockets, process details, settings, anomaly injection, restoration, and simulator exports.
- FastAPI and SQLite, bounded histories, validated settings, local-only serving.
- EWMA burst prediction; bounded sliding unigram/bigram/trigram profiles; frozen baselines; normalized statistical scores; confirmation, hysteresis, and recovery states.
- Shared CPU/memory decisions with bounded changes, cooldowns, fairness input, outcome deltas, readback, and rollback journal.
- Linux BCC C tracepoints and ring buffer; explicit managed-thread filtering; `/proc` and cgroup supplements. Missing eBPF is a visibly labeled fallback, or a hard error with `--require-ebpf`.
- FIFO, LRU, LRU-K, and a documented BARG hybrid page-reference simulator.
- Bounded disposable CPU, memory, file-I/O, and anomaly workloads. Randomized repeated Linux trials for vanilla, monitoring, CPU, memory, and full BARG.

**Verification:** Windows userspace tests and frontend build were executed. Ubuntu kernel attachment, cgroup writes, rollback on a real kernel, and Linux experiment results require VM execution. See [verification record](docs/VERIFICATION.md) and [acceptance matrix](docs/ACCEPTANCE.md).

## Repository

```text
barg/             Python package: model, profiler, control, engine, collector,
                  agent, backend, store, simulator, workload, evaluate
ebpf/telemetry.c  BCC scheduler/syscall/optional page-fault tracepoints
frontend/         React/TypeScript dashboard; Vite and Tailwind
scripts/          Ubuntu setup, capability checks, launch, tests, cleanup
tests/            Algorithms, state transitions, rollback, API and WebSocket tests
docs/             Architecture, methodology, algorithms, experiments, report, viva
results/          Generated measurements (ignored by Git)
data/             Local SQLite and runtime snapshots (ignored by Git)
```

The Python modules are deliberately small and colocated rather than split into empty subsystem packages.

## Windows development

Use Python 3.12+ and Node 20+ (Node 24 was tested). In PowerShell, from this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn barg.backend:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The current workspace already has dependencies and a built dashboard. `powershell -File scripts/start.ps1` launches it. Stop with Ctrl+C. Do not bind the service to `0.0.0.0`.

For frontend hot reload, run `npm.cmd run dev` in `frontend` while the backend is running. Vite forwards `/api` and `/ws` to localhost:8000. Changing a production frontend requires rebuilding and refreshing the browser.

If Windows sandboxing prevents pytest temporary files or SQLite threads from working, run from an ordinary local terminal. The normal Windows `python.exe` Store alias may not be installed; use a real Python installation. The initially supplied bundled Python lacked working `ensurepip` in the sandbox; dependencies here were installed through its external pip targeting the local virtual environment.

## Ubuntu installation

Copy the source directory to the VM, excluding Windows `.venv` and `frontend/node_modules`. Take a VM snapshot. Allow roughly 2 vCPUs and 4 GiB RAM; keep experiments within the built-in bounds.

Install Node.js 22 or 24 with npm first. Setup rejects Node versions below 20; Ubuntu's default Node package may be too old for the dashboard dependencies.

```bash
bash scripts/setup.sh
bash scripts/check_environment.sh
bash scripts/run_tests.sh
bash scripts/start.sh                   # simulated demo, no sudo
```

Setup installs Ubuntu BCC packages and creates a virtualenv with `--system-site-packages`, so the distro's `bcc` Python module is visible. BCC is chosen for maintainable Ubuntu installation; this is not a libbpf CO-RE implementation. Kernel headers must match the running kernel. Dependencies used on Windows are recorded in `requirements-lock.txt`; `requirements.txt` is portable across Ubuntu packages.

## Live Linux demonstration

The privileged agent runs separately from the unprivileged web server and accepts **no browser commands**. Live settings are intentionally read-only in the dashboard. All live policy changes are explicit CLI options.

```bash
sudo bash scripts/prepare_cgroup.sh
# If this reports missing root controller delegation, consult docs/EXPERIMENTS.md.
mkdir -p data                           # create as ordinary user, before the agent

# Terminal 1: start strict monitoring and produce data/live.json
sudo .venv/bin/python -m barg.agent \
  --root /sys/fs/cgroup/barg-lab --groups worker competitor \
  --mode monitor --require-ebpf --output data

# Terminal 2: launch an authorized bounded workload (drops root before workload execution)
sudo .venv/bin/python -m barg.launch --kind anomaly --duration 60

# Terminal 3: no sudo
BARG_MODE=live bash scripts/start.sh
```

Confirm `eBPF attached`, a positive event count, non-stale samples tagged `linux-ebpf`, and the expected workload identity. Save these observations; attachment alone is not proof of event reception.

Stop the monitoring agent before starting an adaptive agent. Replace `--mode monitor` with `--mode full` to enable CPU, memory, and confirmed anomaly response. Other choices are `cpu` and `memory`. The agent restores originals on Ctrl+C/SIGTERM; a root-owned journal handles interrupted runs. Startup refuses concurrent agents and replays a previous journal before new controls.

```bash
sudo bash scripts/cleanup.sh            # only after agent and workloads stop
```

The sandbox has two leaf groups and never enrolls existing system processes. CPU weights stay within 50–200 with steps of at most 20. Memory protection stays within 0–64 MiB with steps of at most 8 MiB. `memory.max`, proactive reclaim, suspension, and termination are not control actions. Ordinary benchmark process timeouts only terminate the child launched by that benchmark.

## College demo sequence

1. Launch the Windows demo and point out the **SIMULATION MODE** banner.
2. Wait 12 windows for baseline training. Inspect CPU burst predictions and process profiles.
3. In Settings disable monitoring-only; enable CPU, memory, and anomaly response; save.
4. In Security select **Inject safe demo anomaly**. Observe WARNING → ANOMALOUS, a bounded CPU-weight reduction, then RECOVERING → NORMAL and restoration.
5. Inspect Feedback engine for before/after allocations and next-window deltas. These deltas are not causal performance evidence.
6. Run the page-replacement comparison under Experiments; export CSV.
7. Select **Restore original allocations**. For the real OS portion, use the Ubuntu procedure above and show actual tracing and rollback logs separately.

## Experiments and exports

```bash
.venv/bin/python -m barg.evaluate --output results/simulator
sudo bash scripts/prepare_cgroup.sh     # only if no sandbox exists yet
sudo bash scripts/run_benchmarks.sh --repeats 3 --duration 40
```

The Linux matrix runs 60 bounded trials by default (about 45–55 minutes): four workload kinds × five modes × three repeats. The default matrix requires eBPF, pins a workload and CPU competitor to the same allowed CPU, randomizes order with seed 42, and restores between trials. Run **without another agent**. Results are written to `results/linux`, with per-workload CSV/JSON/PNG/Markdown exports and a combined JSON. They are also published in data/experiments.json for read-only access by the Experiments API. Compilation/sysbench/stress-ng are explicitly unavailable in this built-in bounded suite.

API docs: http://127.0.0.1:8000/docs. Export `/api/export/telemetry`, `/api/export/decision`, `/api/export/anomaly`, `/api/export/simulator`, or `/api/export/experiment`; append `?format=csv` for CSV. Live telemetry exports read the agent database; simulator results use the backend database; Linux experiment results use the read-only JSON handoff. Keep `BARG_DATA` aligned with the agent `--output` directory.

## Limitations

This is a research prototype, not an endpoint security product. PID/TID polling can miss very short-lived processes and new threads until the next interval. Syscall sequences are bounded, with truncation reported, and process-wide sequences can mix threads. Baselines are frozen after training; explicitly retrain for legitimate changes (demo API) or restart the live agent. Memory.low is best-effort protection, not a reservation or guaranteed optimization. CPU weights matter under contention. Page-fault telemetry is not a complete reference stream. Simulator traces are synthetic. No superiority, accuracy, zero-overhead, or patentability claim is made.

See the [architecture](docs/ARCHITECTURE.md), [methodology](docs/METHODOLOGY.md), [algorithms](docs/ALGORITHMS.md), [experiment protocol](docs/EXPERIMENTS.md), and [academic report](docs/PROJECT_REPORT.md).
