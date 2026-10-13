# Acceptance and scope

| Requirement | Delivery / qualification |
|---|---|
| Working dashboard/backend | Built and locally launched; browser and WebSocket checks performed |
| Profiling/detection | Implemented and tested on simulated samples |
| Auditable feedback | Shared sample identity, decisions, before/after values and outcome deltas |
| CPU control | cpu.weight, bounds, cooldown, fairness gate, readback and journal; real kernel test pending |
| Memory control | memory.low protection and pressure rollback; no proactive reclaim or high/max tuning |
| eBPF | BCC tracepoints and ring buffer implemented; actual verifier/attachment/event reception pending Ubuntu |
| Fallback | Explicit linux-proc; never relabeled as eBPF or simulated |
| Simulator | FIFO, LRU, LRU-K and locality hybrid; executed synthetic exports |
| Benchmarks | Four bounded built-ins and five Linux modes; Linux matrix unexecuted |
| External benchmarks | Compilation, sysbench, stress-ng unavailable in current harness |
| Privilege boundary | Root CLI agent; local unprivileged dashboard; live writes unavailable through web |
| Settings | Demo settings/retraining/restore APIs; live mode chosen via CLI |
| Metrics | Workload, process accounting, faults/PSI, event delay/loss, control and labeled detection metrics |
| Overhead | Agent accounting does not equal total system overhead; kernel/UI attribution needs external measurement |
| Academic material | Architecture, algorithms, methods, experiments, report, contribution assessment, 48 viva answers |
| Claims | No real-kernel performance or novelty claim without evidence |

Remaining acceptance work requires the Ubuntu VM: strict eBPF startup and positive event reception, real cgroup readback/rollback, repeated Linux trials, analysis of measured outcomes, and replacing the intentionally empty report results table.
