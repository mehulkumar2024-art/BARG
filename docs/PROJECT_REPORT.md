# BARG — Behavior-Aware Resource Governance

## 1. Abstract

BARG investigates a shared behavioral pipeline for CPU resource allocation, memory protection, and statistical anomaly response on Linux. Small BCC eBPF programs observe managed task scheduling and syscall activity. A Python engine maintains EWMA and syscall n-gram profiles, scores deviations, and applies bounded cgroup policies. A React dashboard exposes observations and decisions. A separate synthetic page-reference simulator evaluates replacement policies. Windows userspace verification is available; Linux effectiveness remains subject to the documented Ubuntu experiment protocol.

## 2. Introduction

Schedulers, memory managers and security monitors observe overlapping workload behavior, often through independent mechanisms. Sharing a profile may reduce inconsistent policy decisions and make resource responses easier to audit. The project explores that integration without modifying Linux kernel source.

## 3. Problem statement

Design an executable, bounded and observable feedback loop whose scheduling, memory and anomaly components consume common evidence. Determine whether coordinated responses offer measurable advantages and acceptable costs under reproducible workloads.

## 4. Objectives

Collect actual managed-workload events on supported Linux systems; learn lightweight profiles; detect statistical deviations; safely govern proportional CPU shares and memory protection; measure subsequent behavior; compare configurations; and expose evidence through an interactive dashboard.

## 5. Related work

Linux cgroups provide hierarchical resource controls; BCC provides accessible eBPF tracing infrastructure. EWMA, n-grams, standardized deviations, distribution divergence, and Jain fairness are established techniques. FIFO, LRU and LRU-K are established memory-reference policies. This report does not claim their invention. A full systematic related-work comparison remains future work; primary implementation references appear below.

## 6. Proposed methodology

Use one identity-keyed sample per interval, finite training baselines, bounded score components, temporal confirmation and hysteresis. A joint policy selects CPU and memory targets, then validates scope and bounds before writes. Subsequent CPU/PSI/score deltas are logged. Compare vanilla, monitoring, CPU-only, memory-only and full modes on identical bounded workloads with repeated randomized trials.

## 7. System architecture

The Linux agent owns collection and actuation. FastAPI reads snapshots and records without privileged control access. React renders streaming status and historical records. Simulated mode runs the same profiler and policy against a deterministic telemetry generator and in-memory actuator. See ARCHITECTURE.md for the dataflow and privilege boundaries.

## 8. Algorithms

EWMA predicts CPU bursts. Sliding unigram, bigram and trigram probabilities model syscall behavior. Clipped Z-scores and Jensen-Shannon divergence form a weighted score. Confirmation and recovery windows regulate state changes. Jain's index supplies a fairness gate. A step-limited policy chooses cpu.weight and memory.low targets. ALGORITHMS.md specifies equations and worked examples.

## 9. Implementation details

Python modules implement validated samples, profiling, policies, SQLite, API, Linux collection, workload execution and evaluation. BCC C programs emit structured scheduler/syscall/optional page-fault records through a ring buffer. The frontend uses React, TypeScript, Vite, Tailwind and SVG charts. Ubuntu scripts install dependencies, diagnose capabilities, prepare explicit cgroup leaves and restore allocations.

## 10. Testing

The suite checks mathematical examples, sliding expiry, baseline freeze, confirmation/recovery, control bounds, cooldown, temporary-file rollback, PID reuse, end-to-end demo detection, API validation, WebSocket delivery, origin restrictions, simulator output and labeled evaluation metrics. Linux capability and event-reception tests are separate. See VERIFICATION.md for actual results and unexecuted checks.

## 11. Experimental results

**Real Linux results are not yet available. Intentionally unfilled cells below must be populated only from actual VM runs.**

| Mode | Throughput | Agent CPU/RSS | Fault rate/PSI | Detection metrics | Resource changes | Restoration verified |
|---|---|---|---|---|---|---|
| Vanilla | | | | | | |
| Monitoring | | | | | | |
| CPU only | | | | | | |
| Memory only | | | | | | |
| Full BARG | | | | | | |

Executed synthetic simulator measurements are stored separately under results/simulator. They do not fill the Linux table and do not establish real memory-management improvements.

## 12. Discussion

Auditable integration is implemented, but effectiveness depends on workload, contention and calibration. A lower CPU share can reduce anomalous throughput but also delay benign work. Memory protection can shift reclaim pressure to siblings. False positives therefore have resource-allocation costs. A threshold requiring corroborating features reduces some false positives but can miss isolated syscall deviations.

## 13. Limitations

Live tracing and actuation were not run on the Windows development host. Membership polling misses sufficiently short processes. Syscall truncation and thread interleaving can distort distributions. The policy is heuristic, not an optimizer. The memory policy only adjusts protection. Agent overhead accounting omits some kernel/UI cost. External compilation/sysbench/stress-ng workloads are unavailable. Live dashboard controls are intentionally CLI-only. A broader adversarial evaluation and prior-art study are absent.

## 14. Future scope

Verify and package CO-RE probes; improve event membership tracking; model per-thread syscall baselines; calibrate features on varied benign workloads; add demand-aware fairness; evaluate coordinated policies against independent alternatives; collect systemwide overhead with external instrumentation; and add additional bounded benchmark adapters.

## 15. Conclusion

BARG provides an executable and inspectable research prototype joining behavioral telemetry, anomaly scoring and conservative resource controls. Its academic value depends on honest separation of demonstration, simulator and live-kernel evidence. The supplied experiment workflow is intended to produce that evidence without inventing results.

## 16. References

1. [Linux kernel: Control Group v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html).
2. [BCC reference guide](https://github.com/iovisor/bcc/blob/master/docs/reference_guide.md).
3. [BCC tracing examples](https://github.com/iovisor/bcc).
4. Project implementation and reproducible tests in this repository; formulas are fully specified in ALGORITHMS.md.
