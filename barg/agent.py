"""Privileged, local-only Linux control agent. No socket or HTTP command input."""
import argparse
import json
import os
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
    args = parser.parse_args()
    if os.geteuid()!=0: parser.error('Run the agent as root inside the Ubuntu VM')
    import fcntl
    state_path=Path(args.state)
    if not state_path.exists() or state_path.stat().st_uid!=0 or state_path.stat().st_mode & 0o077:
        parser.error('State directory must be root-owned and mode 0700 (run prepare_cgroup.sh)')
    lock=(state_path/'agent.lock').open('w')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: parser.error('Another BARG agent holds this sandbox lock')
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
    collector = Collector(args.root,args.groups,args.require_ebpf)
    output = Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    store = Store(output/'agent.sqlite3')
    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    started = time.monotonic()
    try:
        while running and (not args.duration or time.monotonic()-started < args.duration):
            samples = collector.collect(settings.interval)
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
            snapshot = engine.snapshot()
            snapshot.update(collector='eBPF attached' if collector.bpf else 'proc fallback',
                            collector_error=collector.error,capabilities=capabilities(),events_received=collector.events)
            import resource
            usage=resource.getrusage(resource.RUSAGE_SELF)
            snapshot['agent_accounting']={'cpu_seconds':usage.ru_utime+usage.ru_stime,'peak_rss_mb':usage.ru_maxrss/1024,
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
