"""BCC ring buffer collector. Only TIDs inside explicit workload leaves are traced."""
import ctypes as ct
import os
import platform
import time
from pathlib import Path
from collections import defaultdict, deque
from barg.model import Sample


def capabilities():
    trace = next((p for p in (Path('/sys/kernel/tracing/events'),Path('/sys/kernel/debug/tracing/events')) if p.exists()),None)
    events = ('sched/sched_switch','sched/sched_process_exit','raw_syscalls/sys_enter','exceptions/page_fault_user')
    return {'platform':platform.system(),'kernel':platform.release(),'cgroups_v2':Path('/sys/fs/cgroup/cgroup.controllers').exists(),
            'btf':Path('/sys/kernel/btf/vmlinux').exists(),'root':hasattr(os,'geteuid') and os.geteuid()==0,
            'tracepoints':{e:bool(trace and (trace/e/'format').exists()) for e in events}}


def proc(pid):
    text = Path(f'/proc/{pid}/stat').read_text()
    end = text.rfind(')')
    values = text[end+2:].split()
    # Array starts at field 3 (state).
    return {'identity':f'{pid}:{values[19]}','pid':pid,'name':text[text.find('(')+1:end],
            'ticks':int(values[11])+int(values[12]),'faults':int(values[7])+int(values[9]),
            'rss':int(values[21])*os.sysconf('SC_PAGE_SIZE')/1024**2}


class Collector:
    def __init__(self, root, groups, require_ebpf=False):
        self.root, self.groups = Path(root), groups
        self.bpf = None
        self.error = None
        self.buffers = defaultdict(lambda:{'bursts':deque(maxlen=4096),'calls':deque(maxlen=8192),'switches':0,'count':0,'faults':0,'truncated':0,'events':0,'latency_ns':0,'timestamps_ns':0})
        self.previous = {}
        self.identities = {}
        self.last = time.monotonic()
        self.events = 0
        try:
            from bcc import BPF
            caps = capabilities()
            required = ('sched/sched_switch','sched/sched_process_exit','raw_syscalls/sys_enter')
            if not all(caps['tracepoints'][e] for e in required): raise RuntimeError('Required tracepoint missing')
            source = (Path(__file__).resolve().parent.parent/'ebpf/telemetry.c').read_text()
            flags = ['-DHAS_PAGE_FAULT'] if caps['tracepoints']['exceptions/page_fault_user'] else []
            self.bpf = BPF(text=source,cflags=flags)
            self.bpf['events'].open_ring_buffer(self.consume)
        except Exception as exc:
            self.error = str(exc)
            if self.bpf:
                self.bpf.cleanup()
                self.bpf = None
            if require_ebpf: raise RuntimeError(f'eBPF required but unavailable: {exc}') from exc

    def consume(self, ctx, data, size):
        event = self.bpf['events'].event(data)
        buf = self.buffers[int(event.tgid)]
        self.events += 1
        buf['events'] += 1
        buf['timestamps_ns'] += int(event.timestamp)
        if event.kind == 1:
            buf['bursts'].append(event.duration/1e6)
            buf['switches'] += 1
        elif event.kind == 2:
            if len(buf['calls'])==buf['calls'].maxlen: buf['truncated'] += 1
            buf['calls'].append(int(event.syscall))
            buf['count'] += 1
        elif event.kind == 3: buf['faults'] += 1

    def members(self):
        result, tids = {}, {}
        for group in self.groups:
            for value in (self.root/group/'cgroup.procs').read_text().split():
                pid = int(value)
                try:
                    record = proc(pid)
                    record['group'] = group
                    record['pressure'] = float((self.root/group/'memory.pressure').read_text().split('avg10=')[1].split()[0])
                    try:
                        io = dict(line.split(': ') for line in Path(f'/proc/{pid}/io').read_text().splitlines())
                        record['io'] = int(io['read_bytes'])+int(io['write_bytes'])
                    except (OSError,KeyError): record['io'] = 0
                    result[pid] = record
                    for tid in Path(f'/proc/{pid}/task').iterdir(): tids[int(tid.name)] = pid
                except (OSError,ValueError,IndexError): continue
        if self.bpf:
            allowed = self.bpf['allowed']
            for key in list(allowed.keys()):
                if key.value not in tids: del allowed[key]
            for tid,pid in tids.items():
                allowed[ct.c_uint(tid)] = ct.c_uint(pid)
        # Discard buffered records on PID reuse; no baseline is inherited.
        for pid,record in result.items():
            if self.identities.get(pid,record['identity']) != record['identity']: self.buffers.pop(pid,None)
        self.identities = {pid:r['identity'] for pid,r in result.items()}
        return result

    def collect(self, interval=1):
        self.members()
        deadline = time.monotonic()+interval
        while time.monotonic()<deadline:
            if self.bpf: self.bpf.ring_buffer_poll(100)
            else: time.sleep(min(.1,max(0,deadline-time.monotonic())))
        members = self.members()
        now = time.monotonic()
        elapsed = now-self.last
        self.last = now
        samples = []
        drops = int(self.bpf['dropped'][ct.c_int(0)].value) if self.bpf else 0
        for pid,record in members.items():
            previous = self.previous.get(record['identity'],record)
            buf = self.buffers[pid]
            bursts = list(buf['bursts'])
            stats = {}
            for name in ('cpu.stat','memory.stat','memory.events'):
                try: stats[name] = {k:int(v) for k,v in (line.split() for line in (self.root/record['group']/name).read_text().splitlines())}
                except (OSError,ValueError): stats[name] = None
            try: stats['memory.current'] = int((self.root/record['group']/'memory.current').read_text())
            except OSError: stats['memory.current'] = None
            samples.append(Sample(identity=record['identity'],pid=pid,name=record['name'],group=record['group'],
                timestamp=time.time(),source='linux-ebpf' if self.bpf else 'linux-proc',
                cpu=max(0,(record['ticks']-previous['ticks'])/os.sysconf('SC_CLK_TCK')/elapsed*100),
                burst_ms=sum(bursts)/len(bursts) if bursts else 0,switches=buf['switches'],
                faults=max(0,record['faults']-previous['faults'])/elapsed,memory_mb=record['rss'],pressure=record['pressure'],
                io_bytes=max(0,record['io']-previous['io'])/elapsed,syscalls=list(buf['calls']),syscall_count=buf['count'],
                drops=drops,sequence_truncated=buf['truncated'],event_count=buf['events'],cgroup_stats=stats,
                event_latency_ms=max(0,(time.monotonic_ns()-buf['timestamps_ns']/buf['events'])/1e6) if buf['events'] else None))
        self.previous = {r['identity']:r for r in members.values()}
        self.buffers.clear()
        return samples

    def close(self):
        if self.bpf: self.bpf.cleanup()
