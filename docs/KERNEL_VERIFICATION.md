# Ubuntu kernel acceptance — 20 October 2026

Result: **2 passed, 0 failed, 0 skipped** on an isolated GitHub-hosted Ubuntu 24.04 VM.

- Tested commit: 1932aee.
- Kernel: 7.0.0-1017-azure, x86_64.
- Run: https://github.com/mehulkumar2024-art/BARG/actions/runs/39433938961
- Artifact: ubuntu-kernel-evidence (capabilities.json, uname.txt, pytest.log, junit.xml).
- Test suite duration: 20.044 seconds.

## Verified

1. BCC compilation and actual tracepoint attachment with require_ebpf=True; received kernel events from the managed I/O workload; samples included syscall counts and scheduler switches. Workload exited successfully.
2. Real cgroup v2 cpu.weight=80 and memory.low=8388608 writes and readback; restored original values and verified exact readback.
3. Cleanup succeeded: rollback attempted, empty worker/competitor sandbox removed.

All required scheduler/syscall tracepoints, optional user page-fault tracepoint, BTF and cgroups v2 were present. Presence of the optional fault tracepoint is not a test of fault-event accuracy.

## Initial failure and correction

The first run passed cgroup restoration and received kernel events, but its CPU hashing workload did not produce an observed syscall sample. The test now uses the existing bounded file-I/O workload, which deliberately makes syscalls and sleeps. No assertions were removed or weakened; a child exit-code assertion was added. First run: https://github.com/mehulkumar2024-art/BARG/actions/runs/39433532999 .

## Scope

This validates the two real-kernel integration tests on the recorded hosted kernel. It does not prove performance gains, detector accuracy, crash recovery, full experimental matrix results or compatibility with every Ubuntu kernel. Hosted runners are disposable and are not the deployed monitoring backend. A private persistent backend and controlled performance experiments remain separate work.
