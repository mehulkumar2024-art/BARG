# Experiment protocol

## Preconditions

Use Ubuntu 24.04 with a recent generic kernel and cgroups v2. Install via setup.sh. Check tracing support and BCC import. Run strict agent startup with `--require-ebpf` before collecting experimental data. A system with unavailable required tracepoints must fail, not silently generate simulated data.

`prepare_cgroup.sh` creates only `/sys/fs/cgroup/barg-lab/{worker,competitor}` and a root-owned authorization manifest. It does not change existing processes or silently change root controller delegation. If CPU/memory are unavailable in root `cgroup.subtree_control`, in a dedicated VM an administrator may explicitly enable them:

```bash
echo '+cpu +memory' | sudo tee /sys/fs/cgroup/cgroup.subtree_control
sudo bash scripts/prepare_cgroup.sh
```

If systemd or another manager owns the hierarchy, establish appropriate delegation rather than repeatedly forcing writes. EBUSY/permission errors are real setup failures. Never run on a shared production host.

## Matrix

| Mode | Collector | CPU policy | Memory policy | Anomaly response |
|---|---|---|---|---|
| vanilla | none | original | original | none |
| monitor | eBPF | original | original | log only |
| cpu | eBPF | behavior-aware | original | disabled |
| memory | eBPF | original | behavior-aware | disabled |
| full | eBPF | behavior-aware | behavior-aware | bounded response |

The harness pins both disposable workload processes to one available CPU, so CPU-share adjustments can be studied under contention. The competitor runs CPU work in its own leaf. The primary workload is CPU, memory, throttled normal file-I/O, or a normal→intense-I/O→normal interval. Each process is launched as a known module, enrolled before exec, and drops to the invoking non-root user's UID/GID. No existing PID is enrolled.

Anomaly labels cover the middle quarter (50–75%) of a trial. At 40 seconds this allows about 20 normal seconds, 10 anomaly seconds, then 10 recovery seconds. Workloads are bounded to 120 seconds, memory to 128 MiB, and 16 disposable files with a footprint below 64 KiB. No encryption, recursive file scanning, deletion of user data, evasion, or persistence is implemented.

```bash
sudo bash scripts/run_benchmarks.sh --repeats 3 --duration 40
```

Order is shuffled with seed 42. Do not run another agent concurrently. Existing run directories are rejected to preserve earlier evidence; choose a new `--output` for a new matrix. Retain VM vCPU/RAM, host, kernel, Python, BCC, Node versions, and relevant background-load notes with the exported records.

## Metrics and interpretation

Measured: workload duration, operation count and throughput; cgroup CPU-time deltas and Jain index; agent CPU time as percent of one core; agent peak RSS; received event rate; kernel output losses; bounded sequence truncation; approximate mean event-to-profile delay; profile processing duration; page-fault rate; PSI; control changes; labeled window TP/FP/TN/FN, precision, recall, false-positive rate, detection latency, and recovery time where observed.

Agent CPU/RSS are process accounting, **not total BARG overhead**: they omit BPF kernel cost, web service, frontend, and measurement perturbation. Compare matched throughput against vanilla as another cost indicator. A failed or missing trial is not zero overhead. Event losses are global collector counters, while event counts are group specific; do not divide the former by a single group's count to claim a global loss rate.

Detection metrics exclude training. False-positive rate is per evaluated window, not per process or day. Undefined denominators return null. Latency for a missed anomaly is null. A legitimate workload transition can look anomalous; this is not malware classification.

Each workload type has separate CSV/JSON/PNG/Markdown files. Never compare raw operation rates across unlike workloads. Compilation, sysbench and stress-ng adapters are not included and appear as unavailable. Add external workloads only after defining bounds, cgroup enrollment, and units.

## Synthetic replacement study

```bash
.venv/bin/python -m barg.evaluate --output results/simulator
```

Seed 42 generates 5,000 references: mostly a 12-page working set interspersed with wider references. Four policies use eight frames and exactly the same trace. This particular trace can produce identical LRU-K and BARG results; report that instead of claiming improvement. Vary seeds, frames, and locality structure before generalizing.

## Evidence checklist

Opt-in kernel acceptance tests (with no other agent or workload running):

```bash
sudo env BARG_KERNEL_TESTS=1 .venv/bin/python -m pytest -q tests/test_kernel_live.py
```

These tests launch a bounded managed workload, require real ring-buffer events, and exercise cgroup readback/restoration. They are skipped by default and were not executed on Windows.

- Save capability output, BCC attachment logs, positive received-event counts, and tagged samples.
- Confirm only managed leaf files changed, readback matched, and originals were restored.
- Retain original per-trial agent SQLite files and logs.
- Separate simulated data, `/proc` fallback data, and strict eBPF data.
- Inspect loss/truncation and training coverage before interpreting detector metrics.
- Report all runs and failures; do not cherry-pick peaks.
- Fill the academic results table only after Ubuntu runs; no Linux performance data was available in the Windows development session.
