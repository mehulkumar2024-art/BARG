# Verification record — 13 October 2026

Development environment: Windows 11, Python 3.12.14, Node 24.13.0. An elevated WSL inventory found only Docker Desktop's distribution, with no dedicated Ubuntu installation. That system distribution was not used for kernel or resource-control tests.

## Passed

- Python regression suite: **39 passed, 3 skipped**, no failing tests. Command: `.venv\Scripts\python.exe -m pytest -q --basetemp=data/test-tmp-7`.
- React/TypeScript production build (`npm run build`), including type checking.
- Python bytecode compilation for application and tests.
- Bash syntax validation of all scripts using the installed Git Bash.
- Real localhost FastAPI server startup and static dashboard serving.
- Browser-observed WebSocket connection and continuously updated process rows.
- Browser settings save and safe synthetic anomaly injection.
- Browser-observed WARNING → ANOMALOUS → RECOVERING → NORMAL transitions.
- Browser-triggered simulator run with persisted FIFO, LRU, LRU-K and BARG results.
- Browser process-detail view and restore confirmation; final dashboard returned to monitoring-only.
- Final responsive dashboard screenshot saved in `docs/screenshots/dashboard.png`.
- API integration tests covering process details, baseline retraining, settings validation, restore, exports, simulator execution, hostile-origin rejection and live-web actuation denial.
- One-second Windows smoke execution of all four bounded workloads; generated private files were cleaned up. Results: `results/userspace-smoke/results.json`.
- Synthetic simulator CSV/JSON/PNG/Markdown export: `results/simulator/`.

## Skipped / unexecuted

Three tests are skipped on Windows: the Linux cgroup capability test, opt-in real tracepoint reception test, and opt-in actual cgroup readback/restore test. Linux BCC compilation, verifier acceptance, attachment, event reception, cgroup actuation and experiment matrix have **not** been verified. Follow EXPERIMENTS.md in an Ubuntu 24.04 VM.

## Development issues and resolution

Initial dependency downloads required network access outside the execution sandbox. Vite's source realpath operation, pytest temporary-directory setup and local integration threads also encountered sandbox limitations. The build and full tests passed when executed in the ordinary local environment. These initial environment errors are not counted as final passing tests until the successful reruns.

The installed Starlette test client emits one deprecation warning about its httpx transport. API tests still pass; this is recorded rather than hidden. `requirements-lock.txt` captures the installed package versions.

Final review also separated kernel losses from sequence truncation in the dashboard, made pressure rollback bypass cooldown, disabled training-time actuation, and separated root-owned experiment output from the unprivileged backend database. Regression tests cover the policy and experiment-handoff changes.

## UI refresh — white and teal

The dashboard was restyled across all views with white surfaces, a teal accent palette, rounded cards, softer shadows, page-entry transitions, animated switches, button hover/press feedback, and visible keyboard focus. Chart series use teal shades and distinct dash patterns. Motion is disabled for the operating system's reduced-motion preference. TypeScript and the production build passed; browser checks confirmed the refreshed overview, settings switches, and analytics navigation.

## Reliability pass

Corrected producer freshness timestamps, malformed live/experiment file handling, SQLite read connection closure, immediate restoration state, exact 20-window demo injection, session-specific demo identities, page-aligned memory targets, measured syscall intervals, optional PSI handling, and steady-state agent CPU accounting. Adaptive Linux modes now require eBPF; memory control fails clearly when pressure telemetry is unavailable. The Linux matrix holds a sandbox lease across vanilla and adaptive trials and cleans up its own children and restores allocations after errors. These Linux orchestration changes have been inspected and compiled, but still require Ubuntu runtime verification.

Browser checks after rebuilding covered all eight views, settings save, the complete synthetic anomaly/recovery sequence, a continuously refreshed process dialog, Escape/focus restoration, simulator completion and restore. Vite preview now proxies API/WebSocket connections on localhost:5173. Windows setup/start scripts have explicit dependency and build diagnostics; Ubuntu setup checks the frontend's actual Node >=20 requirement. Fresh installation on a clean Windows or Ubuntu machine remains unexecuted.

## Evidence interpretation

Simulator hit ratios on the single default synthetic trace were FIFO 0.5406, LRU 0.5428, LRU-K 0.5638, BARG 0.5638. These are actual executions of a simulator, not live kernel measurements. Identical LRU-K/BARG results on this trace provide no evidence of a BARG advantage. Wall-clock timings vary between runs.

The Windows workload checks establish bounded execution and output format only. They cannot establish Linux scheduling improvements, resource-control effectiveness, detection precision on real workloads, or total overhead. The academic report's Linux results table remains intentionally unfilled.
