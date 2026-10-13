# Architecture

```mermaid
flowchart LR
  K[Managed Linux workload] --> T[BCC tracepoints / ring buffer]
  K --> P[/proc and cgroup metrics]
  T --> A[Bounded aggregation]
  P --> A
  A --> B[Identity + EWMA + n-grams]
  B --> D[Statistical detection state]
  D --> C[Joint CPU / memory policy]
  C --> S[Scope, bounds, cooldown, readback]
  S --> K
  B --> Q[SQLite / atomic live snapshot]
  C --> Q
  Q --> F[Unprivileged FastAPI]
  F --> R[React dashboard]
```

## Execution boundaries

The privileged agent is a foreground Linux process with no listening socket. Only its command-line configuration selects actuators. The web server has no path to a live actuator. This intentionally keeps live UI controls read-only. The simulated engine uses an in-memory actuator with the same policy interface.

`model.py` defines validated records and settings. `collector.py` produces one Sample per managed process per interval. Linux identities are `TGID:/proc starttime`, so reused PIDs receive fresh profiles. `profiler.py` keeps a finite baseline and at most 2,048 syscall IDs, plus 120 rows per profile. `engine.py` retains at most 512 profiles, 500 decisions, and 500 alerts. SQLite retains the latest 50,000 records across kinds; export or archive experiment directories for longer retention.

## Collection

`sched_switch` uses a TID-keyed start-time map. A switch-out emits elapsed on-CPU duration, prev/next TID, owner TGID and name. TID keys allow migration between CPUs. `sched_process_exit` removes tracing/start entries. `raw_syscalls:sys_enter` emits syscall IDs. `exceptions:page_fault_user` is conditional on tracepoint availability; `/proc` minor+major fault deltas are the portable rate used by the profile. Virtual addresses are intentionally not collected.

The 256-page ring buffer delivers structured events; kernel failed-output counts are exposed. User-space keeps a maximum of 8,192 syscalls and 4,096 burst observations per process per interval. Sequence truncation is separate from ring-buffer loss. Membership is refreshed each interval; this can miss short-lived threads. First proc deltas are zero and represent initialization, not measured inactivity. Cgroup CPU stats, memory stats/events/current and PSI supplement process samples.

## Control and recovery

One process per cgroup leaf prevents competing per-process controllers from writing the same resource files. Multi-threaded processes are supported as a single identity, but process-wide syscall order can be affected by thread interleaving. Multiple processes in one leaf cause the agent to stop and restore allocations.

The controller snapshots original CPU weight and memory.low before any write; writes the root-owned journal atomically; applies changes; reads back values; and rolls back a failed write. Ctrl+C/SIGTERM invoke restoration. A killed agent cannot execute a signal handler: restart or use cleanup to replay the journal. A nonblocking file lock prevents concurrent agents sharing the state directory. Reboot removes ephemeral cgroups and /run state.

Memory protection is reduced while a confirmed anomalous workload is CPU-throttled, preventing contradictory allocation. A next-window PSI increase exceeding 20 percentage points triggers an immediate return to original allocations, bypassing the normal cooldown. This is a heuristic guardrail; unrelated pressure can trigger it. Training windows do not actuate.

## Persistence and frontend

Demo telemetry and decisions are persisted by the web service. The Linux agent writes its own SQLite file and atomically replaces live.json. The web process reads these files, serves static production assets and local JSON APIs, and streams one snapshot per interval over WebSockets. Live data staleness is visible. Origin and Host validation complement binding to loopback; this service is not designed for public hosting or multi-user authentication.
