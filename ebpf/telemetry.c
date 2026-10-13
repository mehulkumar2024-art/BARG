#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

struct event_t {
    u64 timestamp;
    u64 duration;
    u32 tid;
    u32 tgid;
    u32 kind;
    s32 syscall;
    u32 prev;
    u32 next;
    char comm[TASK_COMM_LEN];
};
BPF_HASH(allowed, u32, u32, 4096);
BPF_HASH(starts, u32, u64, 4096);
BPF_ARRAY(dropped, u64, 1);
BPF_RINGBUF_OUTPUT(events, 256);

static int emit(struct event_t *event) {
    int result = events.ringbuf_output(event, sizeof(*event), 0);
    if (result < 0) {
        u32 zero = 0;
        u64 *counter = dropped.lookup(&zero);
        if (counter) __sync_fetch_and_add(counter, 1);
    }
    return 0;
}

TRACEPOINT_PROBE(sched, sched_switch) {
    u64 now = bpf_ktime_get_ns();
    u32 prev = args->prev_pid, next = args->next_pid;
    u32 *owner = allowed.lookup(&prev);
    if (owner) {
        u64 *start = starts.lookup(&prev);
        if (start && now >= *start) {
            struct event_t event = {};
            event.timestamp = now;
            event.duration = now - *start;
            event.tid = prev;
            event.tgid = *owner;
            event.kind = 1;
            event.prev = prev;
            event.next = next;
            bpf_probe_read_kernel_str(event.comm, sizeof(event.comm), args->prev_comm);
            emit(&event);
        }
        starts.delete(&prev);
    }
    if (allowed.lookup(&next)) starts.update(&next, &now);
    return 0;
}

TRACEPOINT_PROBE(raw_syscalls, sys_enter) {
    u64 id = bpf_get_current_pid_tgid();
    u32 tid = (u32)id;
    if (!allowed.lookup(&tid)) return 0;
    struct event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.tid = tid;
    event.tgid = id >> 32;
    event.kind = 2;
    event.syscall = args->id;
    bpf_get_current_comm(event.comm, sizeof(event.comm));
    return emit(&event);
}

TRACEPOINT_PROBE(sched, sched_process_exit) {
    u32 tid = (u32)bpf_get_current_pid_tgid();
    starts.delete(&tid);
    allowed.delete(&tid);
    return 0;
}

#ifdef HAS_PAGE_FAULT
TRACEPOINT_PROBE(exceptions, page_fault_user) {
    u64 id = bpf_get_current_pid_tgid();
    u32 tid = (u32)id;
    if (!allowed.lookup(&tid)) return 0;
    struct event_t event = {};
    event.timestamp = bpf_ktime_get_ns();
    event.tid = tid;
    event.tgid = id >> 32;
    event.kind = 3;
    return emit(&event);
}
#endif
