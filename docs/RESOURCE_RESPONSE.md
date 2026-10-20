# Resource incidents and bounded response

BARG detects resource disturbances from real psutil samples. This is a resource stability feature, not antivirus or proof of malicious behavior.

## Detection

- Process CPU: six baseline readings, at least 80% of one core, at least 50 percentage points above the EWMA baseline, and at least twice baseline.
- System pressure: CPU or RAM utilization at least 90%.
- Memory growth: at least 32 MiB/s between samples while system memory usage is at least 85%.
- Two consecutive triggers open an incident; three clear readings recover it. A process exit closes its active incident without claiming recovery.
- CPU baselines freeze during detected spikes; process identity includes creation time. Gaps longer than 30 seconds restart process baseline training.
- Incident events persist in the system SQLite database and are available through Export incident history. The on-screen timeline covers the current backend session.

## Windows stabilization

Launch only a workload you want BARG to manage. From the repository directory:

```powershell
.\.venv\Scripts\python.exe -m barg.guard -- python your_workload.py
```

Replace the command after `--` with your actual workload command. No shell expansion is performed. The directly launched process is the only target; subprocesses are not controlled. Do not use this for an elevated or critical system program.

The supervisor samples every second. Three consecutive readings with workload CPU >=80% of one core and total system CPU >=85% trigger below-normal scheduling priority. The lease expires after 20 seconds; restoration is followed by a 30-second cooldown. Lower priority gives competing programs preference; it is not a CPU cap and does not guarantee a utilization drop. This response is independent of the longer dashboard sampling cadence.

The supervisor verifies current priority before applying/restoring. External priority changes are preserved. Normal exit and Ctrl+C attempt restoration. Abrupt supervisor termination, power loss or permission loss cannot guarantee restoration. The dashboard flags a stale heartbeat; inspect the supervisor terminal and Task Manager if this happens. Reports are written atomically to data/guard-*.json. Run supervisor and backend with the same data directory.

No memory is forcibly freed, no processes are suspended or killed, and no host-wide policy is changed. High memory pressure generates observations and recommendations. Use the existing Ubuntu cgroup agent for Linux resource enforcement.

## Reading the dashboard

Security and Feedback engine show confirmed incident counts, baseline coverage, incident evidence and recovery events. Guarded workload cards show observation/relief/error state and recent actions. Reports older than five seconds are marked stale instead of presenting response state as current.

After updating, restart the Python backend and refresh the browser. Detection runs automatically; automatic priority response requires launching the chosen workload with the guard command.

## Validation and limits

Deterministic tests cover confirmation, persistent spike baseline freezing, recovery, exited processes, lease expiry, cooldown and preserving external changes. Real Windows process priority restoration is checked on a disposable child process. These checks demonstrate functionality, not a benchmark improvement or a guarantee of system stability. Detector thresholds are fixed backend policy; browser watchlist preferences do not change them.
