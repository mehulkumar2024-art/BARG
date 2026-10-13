# BARG: what it does and how to run it

## 1. Understand the project

BARG means **Behavior-Aware Resource Governance**. It is an operating-systems research prototype that observes a workload, learns its usual behavior, detects sustained changes, and can adjust that workload's CPU share and memory protection on Linux.

It has three parts:

| Part | Job | Runs on |
|---|---|---|
| React dashboard | Shows charts, process profiles, alerts, decisions and experiments | Web browser |
| Python backend | Serves the dashboard, streams updates, stores records and runs the simulator | Windows demo or Ubuntu |
| Linux agent | Collects actual eBPF events and applies bounded cgroup settings | Ubuntu, with root privileges |

The browser is the interface. Keep the backend running while using it. Uploading the frontend to GitHub Pages alone does not run the Python backend or Linux agent. The current app uses same-origin `/api` and `/ws` connections and is configured for local access.

## 2. What happens, step by step

1. **Collect:** in demo mode Python generates three synthetic processes. In live mode the agent traces only workloads in the designated cgroups. It combines scheduler/syscall events with `/proc` and cgroup counters.
2. **Train:** each process gets a baseline from its first 12 sampling windows by default. Resource changes are disabled during training.
3. **Predict:** an exponentially weighted moving average (EWMA) estimates CPU burst duration. Recent bursts receive more weight.
4. **Compare:** BARG compares bursts, page faults, I/O and syscall sequences against the baseline. A score indicates behavioral deviation; it is not a probability of malware.
5. **Confirm:** three consecutive high-score windows confirm an anomaly. Lower scores must persist before the state recovers, reducing rapid state changes.
6. **Respond:** monitoring mode records decisions only. Adaptive modes can change relative CPU weight or best-effort memory protection within project bounds. CPU weight is not a CPU percentage; its effect depends on contention.
7. **Observe and restore:** the controller records before/after values and subsequent observations. It can roll back on worsening pressure, and the agent restores original settings on normal shutdown. A journal supports recovery after interruption.
8. **Evaluate:** compare vanilla Linux, monitoring, CPU-only, memory-only and full BARG using repeated controlled trials. The separate page-replacement simulator compares FIFO, LRU, LRU-K and BARG on synthetic references.

Linux keeps its own scheduler and page replacement implementation. BARG adjusts existing resource controls; the simulator does not replace Linux's memory manager.

## 3. Open the working Windows demo

This workspace already contains installed dependencies and the built frontend. Open PowerShell:

```powershell
cd "C:\Users\Mehul\Desktop\os project"
powershell -File scripts/start.ps1
```

Open **http://127.0.0.1:8000/** in your browser. Keep the terminal open. Stop with **Ctrl+C**. If it is already running, simply open the URL instead of starting a second server.

For a fresh checkout, install Python 3.12 with its launcher and Node.js 22 or 24 with npm, reopen PowerShell, then run:

```powershell
git clone https://github.com/mehulkumar2024-art/BARG.git
cd BARG
powershell -File scripts/setup.ps1
powershell -File scripts/start.ps1
```

If Python is installed without the `py` launcher, pass its actual executable path to `scripts/setup.ps1 -Python`. Do not copy a Windows virtualenv into Ubuntu.

## 4. Demonstrate every feature

1. **Overview:** confirm “Stream connected” and “SIMULATION MODE.” CPU, memory and process rows should update about once per second.
2. **Processes:** wait until training finishes. Click a process to see its identity, measurements and burst history. Escape closes the dialog. “Retrain baseline” starts new training and restores allocations before retraining.
3. **CPU analytics:** compare observed bursts with EWMA predictions. Read CPU share and fairness values.
4. **Memory analytics:** inspect RSS, fault rate and pressure. The demo values are synthetic.
5. **Settings:** turn off Monitoring Only; turn on CPU Enabled, Memory Enabled and Anomaly Response. Click **Save configuration**.
6. **Security:** click **Inject safe demo anomaly**. This creates exactly 20 anomalous sampling windows for the synthetic file worker. Watch WARNING → ANOMALOUS, then RECOVERING → NORMAL after the shift ends.
7. **Feedback engine:** inspect decision reasons, before/after allocations and cooldown behavior. An observation following a decision does not prove the decision caused it.
8. **Experiments:** select the number of frames and click **Run comparison**. Four results appear and are saved. Use CSV to export. Linux experiments remain “NOT MEASURED” until real trials are available.
9. **Settings:** click **Restore original allocations**. This restores demo allocations, clears pending controller feedback and enables monitoring-only mode.

At the default one-second interval, allow around 12 seconds for training and roughly 30 seconds for the injected shift and recovery. Different settings change these timings.

## 5. Set up the real Ubuntu implementation

Use a dedicated Ubuntu 24.04 VM with approximately 2 vCPUs, 4 GiB RAM and sufficient disk space for dependencies and results. Take a VM snapshot. Kernel tests have not been executed on this Windows machine.

Install Node.js 22 or 24 with npm in Ubuntu using the instructions at https://nodejs.org/en/download. The setup script checks for Node >=20 because the frontend's Tailwind dependency requires it. Then, inside Ubuntu:

```bash
git clone https://github.com/mehulkumar2024-art/BARG.git
cd BARG
bash scripts/setup.sh
bash scripts/check_environment.sh
bash scripts/run_tests.sh
sudo bash scripts/prepare_cgroup.sh
mkdir -p data
```

Setup installs the Ubuntu BCC packages and matching kernel headers, builds the frontend, and creates a Linux virtualenv that can access the distribution's BCC module. A setup error must be resolved before proceeding. If controller delegation is missing, follow the explicit VM-only instructions in [EXPERIMENTS.md](EXPERIMENTS.md).

### Terminal 1: collect real events

Run from the Ubuntu repository directory:

```bash
sudo .venv/bin/python -m barg.agent \
  --root /sys/fs/cgroup/barg-lab \
  --groups worker competitor \
  --mode monitor --require-ebpf --output data
```

This agent observes without tuning. Required eBPF attachment failures stop startup rather than generating substitute data.

### Terminal 2: start a bounded workload

```bash
sudo .venv/bin/python -m barg.launch --kind anomaly --duration 60
```

The launcher enrolls only its newly launched process, drops root, and runs the controlled workload for 60 seconds. Other choices are `cpu`, `memory` and `io`.

### Terminal 3: open the browser interface

```bash
BARG_MODE=live bash scripts/start.sh
```

Open **http://127.0.0.1:8000/** in the **Ubuntu VM's browser**. Windows localhost points to Windows, not automatically to the VM. For this procedure, use the VM browser without changing network exposure.

Confirm **LIVE LINUX TELEMETRY**, **eBPF attached**, fresh timestamps and positive received-event counts while the workload runs. An empty process table after a workload finishes is expected. Live settings are read-only; privileged controls are configured in the agent terminal.

### Enable adaptive operation

Stop Terminal 1 with Ctrl+C, let restoration complete, and restart the same command with `--mode full`. Launch another workload in Terminal 2. Adaptive modes require eBPF; memory control also requires pressure telemetry. The built-in memory workload may not create enough pressure to trigger memory protection, which is a legitimate result.

For repeatable CPU contention, use the experiment suite below; CPU weights have little visible effect when one process has an otherwise idle CPU.

## 6. Collect real experimental evidence

Stop the standalone agent and wait for workloads to finish. Keep the empty prepared sandbox. Run the opt-in kernel checks:

```bash
sudo env BARG_KERNEL_TESTS=1 .venv/bin/python -m pytest -q tests/test_kernel_live.py
```

Require successful event reception and cgroup readback/restore before claiming the Linux implementation is validated. Then run a small first matrix:

```bash
sudo bash scripts/run_benchmarks.sh --repeats 1 --duration 40 --output results/linux-first
```

This performs 20 trials: four workloads × five configurations. Use `--repeats 3` with a new output directory for the full 60-trial matrix. Do not reuse an existing results directory. The matrix holds one sandbox lock across all modes, including the vanilla baseline, to exclude other agents.

Results include per-trial logs and SQLite data, CSV/JSON tables, PNG charts and summaries. `data/experiments.json` supplies the dashboard's recorded Linux results. Restarting the backend in demo mode can display those records too; each record remains labeled as a real Linux experiment.

For simulator output on Windows:

```powershell
.\.venv\Scripts\python.exe -m barg.evaluate --output results/simulator
```

The simulator is a separate algorithm study. Its hit ratio is not a measured Linux page-cache hit rate. Report negative, identical and missing results honestly.

## 7. Shut down and restore

1. Let workloads finish; stop the agent with Ctrl+C and inspect its terminal for restoration errors.
2. Stop the web server with Ctrl+C.
3. In Ubuntu, run `sudo bash scripts/cleanup.sh` once no agent or workload is running.
4. If the agent was forcibly interrupted, run its `--restore` command before cleanup:

```bash
sudo .venv/bin/python -m barg.agent \
  --root /sys/fs/cgroup/barg-lab --groups worker competitor --restore
```

Do not delete a rollback journal to silence an error; it holds original values needed for restoration.

## 8. Common problems

| Symptom | What to do |
|---|---|
| Browser cannot connect | Start the backend and keep the terminal open. Open port 8000, not a local HTML file. |
| Port 8000 already in use | Open the running dashboard; stop the existing BARG server with Ctrl+C before launching another. |
| Dashboard has not been built | Run the setup script; restart the backend after the frontend build completes. |
| UI shows old changes | Rebuild with `npm.cmd run build` inside `frontend`, then refresh the browser. |
| Stream disconnected | Check backend output. The dashboard reconnects automatically when the server returns. |
| Stale live telemetry | Check the agent terminal, output directory and `BARG_DATA`. Values are historical until updates resume. |
| No Linux processes | Launch a managed workload; the agent does not trace every process on the machine. |
| eBPF/BCC import or attachment error | Verify distro BCC packages, matching kernel headers and the `--system-site-packages` virtualenv. Preserve the exact error. |
| Another agent holds the lock | Stop the existing agent or experiment normally; do not remove its lock file. |
| Missing pip on Windows | Use a standard Python installation for fresh setup. This development machine's bundled runtime required an external pip installer. |
| Corrupt experiment file | Restore the JSON from saved trial results. The API reports an actionable 503 error instead of crashing. |

## 9. Explain it in a presentation

“BARG is a behavior-aware resource governance prototype. It profiles managed workloads using CPU bursts, page faults, I/O and syscall patterns. Sustained deviations produce explainable anomaly scores. A bounded controller can adjust relative CPU shares and memory protection, observe later behavior and restore original settings. A web dashboard displays the pipeline, and repeated Linux experiments evaluate it against vanilla and monitoring-only baselines.”

Show the Windows demo as a demonstration of the interface and algorithms. Present live tracing, performance improvements and detection accuracy only after the Ubuntu tests and experiments produce evidence. See [VERIFICATION.md](VERIFICATION.md) for what has actually been run.
