# Viva questions and answers

1. **What is BARG?** A user-space closed-loop resource-governance prototype driven by shared Linux behavioral telemetry.
2. **What problem does it investigate?** Whether CPU, memory and anomaly policies benefit from common observations and coordinated decisions.
3. **Does it replace the Linux scheduler?** No. It changes supported proportional CPU weights within managed cgroups.
4. **What is a process?** An executing program with an address space and OS-managed resources; threads share much of that state.
5. **What is a context switch?** The CPU changes the executing task, saving/restoring execution context and scheduler state.
6. **What are common process states?** Running/runnable, sleeping, stopped and zombie; Linux exposes more detailed state codes.
7. **What is a CPU burst?** A period of task execution between scheduling transitions in this implementation; it is an estimate from observed switch pairs.
8. **How are migrations handled?** Burst start timestamps are indexed by TID, not by CPU number.
9. **Why might a burst be missing?** A task may be missed by membership polling, tracing may start mid-burst, or events may be dropped.
10. **What is CFS?** Linux's historical fair scheduling design based on weighted virtual runtime. Modern kernels may use EEVDF selection in the fair class; BARG relies on cgroup interfaces rather than scheduler internals.
11. **What is cpu.weight?** A relative share among sibling cgroups competing for CPU, not an absolute guaranteed percentage.
12. **Why might a weight change have no effect?** There may be no CPU contention, or an ancestor's policy may dominate.
13. **What is cpu.max?** A bandwidth quota interface. It is not used by the default project policy.
14. **What is cgroups v2?** Linux's unified hierarchy for grouping processes and managing supported resources.
15. **Why use separate workload leaves?** It prevents different per-process policies from fighting over one shared group setting.
16. **What is virtual memory?** Per-process virtual addresses mapped to physical memory or other backing storage by the OS.
17. **What is a page fault?** An exception when an access cannot proceed through the current page-table mapping; it is not necessarily a disk access.
18. **Minor versus major faults?** Major faults require I/O to satisfy; minor faults do not require that backing-storage I/O.
19. **Can fault rate reveal cache hit ratio?** No. It does not expose all page references, so a denominator for exact hit ratio is absent.
20. **What is memory.low?** Best-effort reclaim protection subject to hierarchy and available memory, not reserved physical RAM.
21. **Why avoid memory.max?** Reducing it routinely can force allocation failure or OOM behavior, inappropriate for this conservative controller.
22. **What is PSI?** Pressure Stall Information reports time tasks are stalled on a resource; BARG reads memory some avg10.
23. **What is FIFO replacement?** Evict the oldest resident insertion regardless of recent hits.
24. **What is LRU?** Evict the page whose last reference was least recent.
25. **What does LRU-K add?** It uses the Kth most recent reference and distinguishes immature pages with fewer than K references.
26. **Is the simulator controlling Linux pages?** No. It evaluates declared synthetic references independently of live governance.
27. **What is eBPF?** A Linux execution facility for verified programs attached to supported hooks, with constrained access through maps and helpers.
28. **What does the verifier do?** It checks program safety properties before loading; successful compilation does not guarantee successful verification or attachment.
29. **Why BCC?** Ubuntu packages simplify compiling small tracing programs against the installed kernel. CO-RE packaging is a possible future improvement.
30. **What is a tracepoint?** An explicit kernel instrumentation hook exposing event fields at a defined location.
31. **Why use a ring buffer?** It transports structured events from kernel to user space with bounded capacity and observable output failures.
32. **What is a syscall?** A controlled user-to-kernel request such as read, write or openat.
33. **Why syscall n-grams?** They capture local ordering patterns beyond simple total call counts.
34. **What is EWMA?** A recursive exponentially weighted average that trades responsiveness against smoothing through alpha.
35. **Why freeze a baseline?** Continual adaptation during assessment could learn anomalous activity as normal.
36. **What is a Z-score?** A standardized deviation from baseline mean; BARG adds a variance floor and clips the normalized score.
37. **Why Jensen-Shannon divergence?** It compares probability distributions symmetrically with a bounded base-two score and finite behavior for unseen sequences.
38. **What is hysteresis?** Different conditions for entering and leaving an alert state prevent rapid oscillation near one threshold.
39. **What is a cooldown?** A minimum time between control changes that limits adjustment frequency.
40. **What does Jain's index measure?** Equality of nonnegative allocations or usages; it does not by itself encode demand or priority.
41. **What is closed-loop feedback?** Measuring the system after an action and feeding observations into subsequent decisions.
42. **Why keep a rollback journal?** In-memory original values disappear if an agent crashes; a durable journal supports later restoration.
43. **How is PID reuse handled?** PID plus process starttime defines identity; a new starttime creates a new baseline.
44. **What are precision and recall?** Precision is TP/(TP+FP); recall is TP/(TP+FN), with undefined cases reported as null.
45. **What is the false-positive denominator?** Evaluated normal windows, excluding training; it is not a per-day or per-machine probability.
46. **Does simulation prove kernel functionality?** No. Real attachment, event reception, cgroup readback and rollback require Linux verification.
47. **How is overhead evaluated?** Agent CPU/RSS accounting plus matched workload measurements; neither alone captures every kernel and frontend cost.
48. **What limits the novelty claim?** The components are established; the integration and heuristic policy need comparison and prior-art evaluation before stronger claims.
