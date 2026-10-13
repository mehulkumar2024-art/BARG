# Methodology

The research question is whether a common behavior profile can coordinate CPU shares, memory protection, and anomaly response more consistently than independent resource policies. An experiment must establish both benefit and cost; implementation alone is not proof.

Each interval observes CPU time deltas, average captured CPU bursts, switches, fault rate, RSS, cgroup PSI, physical read/write-byte deltas, and bounded syscall sequences. CPU utilization is percent of one core and can exceed 100 for a multithreaded process. Wall timestamps support UI alignment; monotonic clocks measure duration and event latency. Burst predictions are compared with the previous EWMA, avoiding comparison against a predictor already updated with the current observation.

The first configured number of windows builds numeric and n-gram baselines. Training samples are not classified as anomalies. Subsequent samples do not modify those baselines. Numeric deviations are scaled by six standard deviations and clipped to one; Jensen-Shannon divergence is already bounded. A weighted sum yields the composite score. Three consecutive high windows confirm an anomaly; three low windows enter recovery and six return to normal. Low means below 60% of the main threshold.

The joint policy prioritizes scope and boundedness before behavioral allocation. Confirmed anomalies receive a target CPU weight of 50 only with explicit response enablement. Otherwise latency-sensitive workloads can target 120 when observed Jain fairness is at least .8; other workloads target 100. Memory.low targets one quarter of observed RSS, capped at 64 MiB, when PSI exceeds 5%. Suspicious workloads target zero protection. Defaults monitor only.

CPU use and PSI are measured after a change and included in the next decision record. These observations cannot alone establish causation. Cooldowns, step limits, narrow ranges, hysteresis, and rollback reduce instability. The heuristic does not solve a formal multi-objective optimization problem and has no stability proof.

Compare five configurations with the same seeded workload, CPU affinity, memory bounds, competing workload, duration, and VM configuration. Randomize trial order and repeat. Keep raw logs; report median and spread for each workload separately. Assess detector quality using labeled intervals and exclude training windows. Report undetected intervals as missing latency, not zero. Sequence loss/truncation weakens detection validity and should accompany results.

Simulator hit/miss ratios are measured on an explicitly synthetic reference stream. Linux faults are separate measurements. Cold cache, scheduler state, VM interference, thermal effects, page-cache reuse, and Python runtime overhead are potential confounders. Do not attribute a difference solely to BARG without controlling them.
