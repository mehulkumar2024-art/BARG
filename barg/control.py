"""Bounded joint policy; adapters isolate privileged writes from the web server."""
from pathlib import Path
import json
import os
import time


class SimulatedActuator:
    page_size = 4096
    def __init__(self):
        self.values = {}
        self.original = {}

    def read(self, group):
        return self.values.setdefault(group, {"cpu.weight": 100, "memory.low": 0}).copy()

    def apply(self, group, changes):
        current = self.read(group)
        self.original.setdefault(group, current.copy())
        self.values[group].update(changes)
        return self.read(group)

    def restore(self):
        self.values.update({k: v.copy() for k,v in self.original.items()})
        return self.values.copy()


class CgroupActuator:
    def __init__(self, root, journal):
        self.page_size = os.sysconf('SC_PAGE_SIZE') if hasattr(os, 'sysconf') else 4096
        self.root = Path(root).resolve()
        if self.root.parent != Path('/sys/fs/cgroup') or not self.root.name.startswith('barg-'):
            raise ValueError('Only a direct /sys/fs/cgroup/barg-* sandbox is authorized')
        # cgroupfs cannot contain arbitrary files: authorization lives in root-owned state.
        marker = Path(journal).parent/'authorized-root'
        if not marker.exists() or marker.is_symlink() or marker.read_text().strip() != str(self.root):
            raise ValueError('Missing explicit authorized-root manifest')
        if marker.stat().st_uid != 0 or marker.stat().st_mode & 0o022:
            raise ValueError('Authorization manifest must be root-owned and not writable by others')
        self.journal = Path(journal)
        self.original = json.loads(self.journal.read_text()) if self.journal.exists() else {}

    def path(self, group):
        if not group or '/' in group or '\\' in group or group in ('.','..'):
            raise ValueError('Invalid workload group')
        path = self.root/group
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError('Cgroup escapes authorized root')
        return path

    def read(self, group):
        path = self.path(group)
        return {k: int((path/k).read_text().strip()) for k in ('cpu.weight','memory.low')}

    def apply(self, group, changes):
        if set(changes)-{'cpu.weight','memory.low'}:
            raise ValueError('Unsupported control')
        if 'cpu.weight' in changes and not 50 <= changes['cpu.weight'] <= 200:
            raise ValueError('CPU weight outside project bounds')
        if 'memory.low' in changes and not 0 <= changes['memory.low'] <= 64*1024**2:
            raise ValueError('Memory protection outside project budget')
        current = self.read(group)
        self.original.setdefault(group, current)
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.journal.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.original))
        temporary.replace(self.journal)
        try:
            for key, value in changes.items():
                (self.path(group)/key).write_text(str(value))
            result = self.read(group)
            if any(result[k] != v for k,v in changes.items()):
                raise RuntimeError('Kernel readback mismatch')
            return result
        except Exception:
            for key,value in current.items():
                (self.path(group)/key).write_text(str(value))
            raise

    def restore(self):
        errors = {}
        for group, values in self.original.items():
            try:
                for key,value in values.items():
                    (self.path(group)/key).write_text(str(value))
                if self.read(group) != values:
                    raise RuntimeError('Restore readback mismatch')
            except Exception as exc:
                errors[group] = str(exc)
        if errors:
            raise RuntimeError(f'Rollback incomplete; journal retained: {errors}')
        self.journal.unlink(missing_ok=True)
        self.original.clear()
        return {'restored': True}


class Controller:
    def __init__(self, actuator):
        self.actuator = actuator
        self.last = {}
        self.pending = {}

    def decide(self, row, settings, fair=1., now=None):
        now = time.monotonic() if now is None else now
        group = row['group']
        before = self.actuator.read(group)
        target = before.copy()
        reason = 'monitoring only' if settings.monitoring_only else 'cooldown: observe without adjustment'
        outcome = None
        previous = self.pending.pop(group, None)
        if previous:
            outcome = {'cpu_delta': row['cpu']-previous['cpu'], 'pressure_delta': row['pressure']-previous['pressure'],
                       'score_delta': row['score']-previous['score'], 'causal_claim': False}
        if not settings.monitoring_only and row.get('training',False):
            reason = 'training: observe without adjustment'
        elif not settings.monitoring_only and outcome and outcome['pressure_delta'] > 20:
            target = self.actuator.original.get(group, before).copy()
            reason = 'rollback: pressure worsened after previous action'
        elif not settings.monitoring_only and now-self.last.get(group, -1e9) >= settings.cooldown:
            suspicious = row['status'] == 'ANOMALOUS' and settings.anomaly_response
            reason = 'confirmed anomaly' if suspicious else 'bounded behavior allocation / recovery'
            if settings.cpu_enabled:
                desired = 50 if suspicious else (120 if row['classification']=='latency-sensitive' and fair >= .8 else 100)
                target['cpu.weight'] = max(50, min(200, before['cpu.weight']+max(-20, min(20, desired-before['cpu.weight']))))
            if settings.memory_enabled:
                desired = 0 if suspicious else (min(64, row['memory_mb']*.25)*1024**2 if row['pressure'] > 5 else 0)
                step = 8*1024**2
                target['memory.low'] = int(before['memory.low']+max(-step, min(step, desired-before['memory.low'])))
                # cgroupfs rounds to kernel pages; write aligned values for exact readback.
                page_size = self.actuator.page_size
                target['memory.low'] = target['memory.low'] // page_size * page_size
        changes = {k:v for k,v in target.items() if before[k] != v}
        result = self.actuator.apply(group, changes) if changes else before
        if changes:
            self.last[group] = now
            self.pending[group] = row.copy()
        return {'timestamp': row['timestamp'], 'identity': row['identity'], 'group': group, 'source': row['source'],
                'reason': reason, 'before': before, 'after': result, 'changes': changes, 'outcome': outcome, 'fairness': fair}
