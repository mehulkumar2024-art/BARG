# Research contribution and prior-art boundary

Established techniques include scheduler tracepoints, eBPF ring buffers, cgroups proportional CPU shares, memory.low protection, EWMA predictors, syscall n-grams, Z-scores, Jensen-Shannon divergence, Jain fairness, FIFO, LRU, and LRU-K. Combining these does not by itself establish novelty.

The implemented contribution is a shared workload identity and telemetry path feeding a joint resource/anomaly policy, with explicit observation → decision → bounded actuation → next-window outcome records. CPU and memory decisions use the same anomaly state and avoid granting extra memory protection to a workload receiving an anomaly CPU response. The dashboard exposes the entire loop.

Project-specific heuristics are the particular score weights, three/six-window state machine, fairness gate, step limits, pressure rollback rule, and locality-dependent LRU/LRU-K hybrid. They should be presented as design choices to evaluate, not theoretically optimal solutions.

Questions for prior-art evaluation: how similar are these choices to existing autonomic resource managers, syscall anomaly detectors, and feedback schedulers; does coordination improve outcomes over independently tuned controllers; and what false-positive and control-stability tradeoffs arise? The current ablation suite separates CPU, memory and full modes, but does not yet isolate every detection/control heuristic.

No patentability or first-of-its-kind claim is made. A literature search, broader workloads, robust baselines, confidence intervals, and live kernel verification are prerequisites for stronger research claims.

Primary implementation references:

- [Linux cgroups v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
- [BCC reference guide](https://github.com/iovisor/bcc/blob/master/docs/reference_guide.md)
- [BCC project and examples](https://github.com/iovisor/bcc)
