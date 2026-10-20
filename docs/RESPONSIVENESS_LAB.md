# Responsiveness experiment lab

Run from the project root in a second PowerShell terminal:

```powershell
.\.venv\Scripts\python.exe -m barg.responsiveness --duration 8 --repeats 3 --target-ms 20
```

Open Experiments in the local dashboard. The backend must be restarted after this feature is installed. Results are read through GET /api/experiments/responsiveness. The web service cannot launch commands or apply this policy.

## Method

Windows only. The lab launches its own foreground and background processes and pins both to one allowed logical CPU. It never changes existing application affinity or priority. Three modes run in a seeded shuffled order: baseline, monitoring only, and adaptive. Default: three repeats of each, eight seconds per trial. Bounds: duration 4–30 seconds; repeats 2–5; target 1–100ms. A lock prevents simultaneous runs within one data directory.

The foreground performs a fixed arithmetic task on a nominal 50ms schedule. Response latency includes wakeup/scheduling delay and completion time. The schedule avoids accumulating an unbounded backlog. The background repeatedly performs a fixed arithmetic loop; its operations/second measure competing throughput. These are synthetic workloads producing actual OS measurements, not simulated telemetry or a real application's response-time benchmark.

All modes include the same worker placement, foreground measurements and basic supervisor loop. Monitor/adaptive additionally sample background CPU and foreground latency every half second. Adaptive lowers only its background worker to below-normal priority after two windows with p95 above the target and background CPU at least 20% of one core. This is an experimental latency policy, distinct from barg.guard's production pressure thresholds. Priority stays reduced for the rest of the bounded trial; cleanup restores it if still alive, otherwise the exited worker has no remaining priority. Only owned test workers may be terminated during failed cleanup.

## Reports

Each run creates data/responsiveness/<unique-id>/report.json and trials.csv. data/responsiveness.json is atomically replaced with the latest progress/result. Reports contain raw latency samples, action/observation timeline, per-trial p50/p95/max, miss fraction, throughput and supervisor process CPU seconds. Summary reports median trial metrics and min/max of trial p95, not a pooled percentile. JSON export is available on the page.

Supervisor CPU time excludes workers, the standalone dashboard and kernel overhead. All three modes still incur experimental harness overhead. The original system monitor and other host applications can interfere. Two short repeats are smoke evidence only; increase repetitions, control host load and report variability before making general claims. Lower latency can trade off against background throughput. No interventions is a valid outcome when policy conditions are not met.

Ctrl+C records a failed/interrupted run and cleans up owned workers. Abrupt OS termination may leave a lock; inspect running lab workers before manually removing data/responsiveness.lock. The UI displays report age rather than treating an old running report as proof of activity.

## Interview demonstration

Start the backend, start the lab command, open Experiments, explain the latency target and three modes, then inspect actions and exported raw measurements. Show both foreground latency and background throughput. Do not present these results as Linux cgroup performance or as a guarantee for arbitrary applications.
