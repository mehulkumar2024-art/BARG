"""Privileged, local-only Linux control agent. No socket or HTTP command input."""
import argparse
import json
import os
import platform
import signal
import time
from pathlib import Path
from barg.collector import Collector, capabilities
from barg.control import CgroupActuator
from barg.engine import Engine
from barg.model import Settings
from barg.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root',required=True)
    parser.add_argument('--groups',nargs='+',required=True)
    parser.add_argument('--state',default='/run/barg')
    parser.add_argument('--output',default='data')
    parser.add_argument('--mode',choices=['monitor','cpu','memory','full'],default='monitor')
    parser.add_argument('--require-ebpf',action='store_true')
    parser.add_argument('--duration',type=float,default=0)
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--lock-fd',type=int,help=argparse.SUPPRESS)
    args = parser.parse_args()
    if platform.system() != 'Linux' or os.geteuid()!=0:
        parser.error('Run the agent as root inside the Ubuntu VM; Windows supports the browser demo')
    if args.duration < 0:
        parser.error('Duration must be nonnegative')
    state_path=Path(args.state)
    if not state_path.exists() or state_path.stat().st_uid!=0 or state_path.stat().st_mode & 0o077:
        parser.error('State directory must be root-owned and mode 0700 (run prepare_cgroup.sh)')
    from barg.locking import acquire
    try: lock = acquire(state_path, args.lock_fd)
    except (RuntimeError, ValueError, OSError) as exc: parser.error(str(exc))
    actuator = CgroupActuator(args.root,Path(args.state)/'rollback.json')
    for group in args.groups: actuator.path(group)
    if args.restore:
        print(actuator.restore())
        return
    # Recover any interrupted previous run before making fresh decisions.
    if actuator.original: actuator.restore()
    settings = Settings(monitoring_only=args.mode=='monitor',cpu_enabled=args.mode in ('cpu','full'),
                        memory_enabled=args.mode in ('memory','full'),anomaly_response=args.mode=='full')
    engine = Engine(settings,actuator)
    collector = Collector(args.root,args.groups,args.require_ebpf or args.mode!='monitor')
    output = Path(args.output)
    try:
        output.mkdir(parents=True,exist_ok=True)
        store = Store(output/'agent.sqlite3')
    except Exception:
        collector.close()
        raise
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    started = time.monotonic()
    import resource
    initial_usage = resource.getrusage(resource.RUSAGE_SELF)
    initial_cpu = initial_usage.ru_utime + initial_usage.ru_stime
    try:
        while running and (not args.duration or time.monotonic()-started < args.duration):
            samples = collector.collect(settings.interval)
            if settings.memory_enabled and not collector.pressure_available:
                raise RuntimeError('Memory control requires cgroup memory.pressure; stopping and restoring allocations')
            active={s.identity for s in samples}
            for identity in set(engine.rows)-active:
                engine.rows.pop(identity,None)
                engine.profiles.pop(identity,None)
            # One workload per leaf is required: avoid multiple policies fighting over a shared leaf.
            groups = [s.group for s in samples]
            if len(set(groups)) != len(groups):
                raise RuntimeError('Use one process per workload leaf for this prototype')
            for sample in samples:
                previous_alert=engine.alerts[-1] if engine.alerts else None
                row,decision = engine.ingest(sample)
                store.add('telemetry',row['timestamp'],row)
                store.add('decision',row['timestamp'],decision)
                if engine.alerts and engine.alerts[-1] is not previous_alert: store.add('anomaly',row['timestamp'],engine.alerts[-1])
            engine.updated_at = time.time()  # Heartbeat also covers an idle managed sandbox.
            snapshot = engine.snapshot()
            snapshot.update(collector='eBPF attached' if collector.bpf else 'proc fallback',
                            collector_error=collector.error,capabilities=capabilities(),events_received=collector.events)
            import resource
            usage=resource.getrusage(resource.RUSAGE_SELF)
            snapshot['agent_accounting']={'cpu_seconds':usage.ru_utime+usage.ru_stime-initial_cpu,'peak_rss_mb':usage.ru_maxrss/1024,
                                          'elapsed_seconds':time.monotonic()-started}
            tmp = output/'live.tmp'
            tmp.write_text(json.dumps(snapshot))
            tmp.replace(output/'live.json')
    finally:
        try:
            collector.close()
        finally:
            try: actuator.restore()
            finally: store.close()


if __name__=='__main__': main()
