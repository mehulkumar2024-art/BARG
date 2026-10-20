"""Run one explicitly chosen Windows workload with reversible CPU priority relief.
Usage: python -m barg.guard -- python your_workload.py
Only the directly launched process is controlled. No shell, process tree or host-wide changes.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import platform
import subprocess
import time
import uuid
import psutil


class PriorityLease:
    def __init__(self, process, original, reduced):
        self.process, self.original, self.reduced = process, original, reduced
        self.until = None
        self.cooldown = 0
        self.high = 0
        self.events = deque(maxlen=100)

    def event(self, action, **details):
        self.events.append(dict(timestamp=time.time(), action=action, **details))

    def restore(self, now):
        if self.until is None:
            return
        # Never overwrite a priority changed by the user or another manager.
        if self.process.nice() == self.reduced:
            self.process.nice(self.original)
            self.event('restored')
        else:
            self.event('external_priority_change', detail='BARG relinquished control')
        self.until = None
        self.cooldown = now+30
        self.high = 0

    def step(self, cpu, pressure, now):
        if self.until is not None:
            if now >= self.until:
                self.restore(now)
            return
        self.high = self.high+1 if cpu >= 80 and pressure >= 85 else 0
        if self.high >= 3 and now >= self.cooldown:
            if self.process.nice() != self.original:
                self.high = 0
                self.event('skipped', detail='Priority differs from initial value')
                self.cooldown = now+30
                return
            # Record the lease before the write so cleanup still attempts restoration on errors.
            self.until = now+20
            self.process.nice(self.reduced)
            self.event('priority_lowered', cpu_percent_one_core=cpu, system_cpu_percent=pressure,
                       lease_seconds=20, detail='Below-normal scheduling; not a CPU cap')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='data')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Supply a workload command after --')
    if platform.system() != 'Windows':
        parser.error('This supervisor supports Windows; use the existing Linux cgroup agent on Ubuntu')
    directory = Path(args.data_dir); directory.mkdir(parents=True, exist_ok=True)
    path = directory/('guard-'+uuid.uuid4().hex+'.json')
    child = subprocess.Popen(command, shell=False)
    try:
        process = psutil.Process(child.pid)
        original = process.nice()
        identity = f'{child.pid}:{process.create_time():.6f}'
    except psutil.NoSuchProcess:
        return child.wait()
    except psutil.Error as exc:
        print(f'Workload launched but guard could not attach: {exc}')
        return 1
    if original != psutil.NORMAL_PRIORITY_CLASS:
        print('Workload launched without guard: only normal-priority workloads are supported.')
        return 1
    lease = PriorityLease(process, original, psutil.BELOW_NORMAL_PRIORITY_CLASS)
    status = 'observing'; cpu = None; pressure = None
    def save():
        payload = dict(timestamp=time.time(), pid=child.pid, identity=identity, status=status,
                       cpu=cpu, system_cpu=pressure, events=list(reversed(lease.events)),
                       priority_reduced=lease.until is not None,
                       scope='Directly launched process only')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload), encoding='utf-8'); temporary.replace(path)
    print(f'BARG guard owns PID {child.pid}. Reports: {path}. Ctrl+C restores priority; no forced termination.')
    try:
        process.cpu_percent(None); psutil.cpu_percent(None)
        save()
        while child.poll() is None:
            time.sleep(1)
            cpu = process.cpu_percent(None); pressure = psutil.cpu_percent(None)
            lease.step(cpu, pressure, time.monotonic())
            status = 'relieving' if lease.until is not None else 'observing'
            save()
        status = 'exited'
    except KeyboardInterrupt:
        status = 'stopped'
    except psutil.NoSuchProcess:
        status = 'exited'
    except (psutil.Error, OSError) as exc:
        status = 'error'; lease.event('error', detail=str(exc))
    finally:
        try:
            lease.restore(time.monotonic())
        except psutil.NoSuchProcess:
            lease.until = None
        except psutil.Error as exc:
            status = 'restore_failed'; lease.event('restore_failed', detail=str(exc))
        save()
    return 1 if status in ('error', 'restore_failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
