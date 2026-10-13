# BARG implementation progress

Environment: Windows, Node 24, bundled Python 3.12. Linux tracing cannot be verified here (WSL access denied).

Implemented: shared profiling/detection; bounded control and rollback; BCC collector and Linux agent; FastAPI/SQLite; eight-view React dashboard; bounded workloads; evaluation/export tooling; tests; Ubuntu scripts; academic documentation. Demo data and Linux measurements are always tagged separately.

Verified: 25 Python tests passed, 3 Linux-only checks skipped; frontend typecheck/production build passed; Bash syntax passed; browser stream, settings, anomaly lifecycle and simulator checked; four Windows workload smoke runs and synthetic simulator exports completed. See docs/VERIFICATION.md.

Remaining environment-dependent acceptance: run scripts/setup.sh and prepare_cgroup.sh on Ubuntu 24.04; execute opt-in tests with BARG_KERNEL_TESTS=1; verify actual received eBPF events and cgroup rollback; run the five-mode repeated experiment matrix; analyze and populate the report results table. Linux execution is blocked by unavailable VM/WSL in this session, not by a claimed test success.

Deliberate scope limits: memory.low policy only (no reclaim/high/max tuning); live privileged control via local CLI instead of browser; external compilation/sysbench/stress-ng adapters unavailable. Total-system overhead needs external measurement beyond agent accounting.
