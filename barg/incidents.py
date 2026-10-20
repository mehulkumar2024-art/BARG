"""Explainable resource incidents; resource anomalies are not malware verdicts."""
from collections import deque
import time
import uuid


class IncidentDetector:
    def __init__(self):
        self.profiles = {}
        self.active = {}
        self.events = deque(maxlen=200)

    def update(self, snapshot):
        now = snapshot['timestamp']
        new = []
        present = set()
        def observe(key, triggered, evidence, kind, identity=None, name='System'):
            present.add(key)
            state = self.active.setdefault(key, {'high': 0, 'low': 0, 'incident': None})
            state['high'] = state['high'] + 1 if triggered else 0
            state['low'] = 0 if triggered else state['low'] + 1
            if triggered and state['high'] >= 2 and state['incident'] is None:
                state['incident'] = uuid.uuid4().hex
                new.append(dict(id=state['incident'], timestamp=now, phase='opened', kind=kind,
                                identity=identity, name=name, evidence=evidence))
            elif state['incident'] and state['low'] >= 3:
                new.append(dict(id=state['incident'], timestamp=now, phase='recovered', kind=kind,
                                identity=identity, name=name, evidence=evidence))
                state['incident'] = None
        system = snapshot['system']
        observe('system:cpu', system['cpu_percent'] >= 90,
                {'cpu_percent': system['cpu_percent'], 'threshold': 90}, 'system_cpu_pressure')
        observe('system:memory', system['memory_percent'] >= 90,
                {'memory_percent': system['memory_percent'], 'threshold': 90}, 'system_memory_pressure')
        live = set()
        for row in snapshot['processes']:
            identity = row['identity']; live.add(identity)
            old = self.profiles.get(identity)
            cpu = row['cpu']
            if cpu is None:
                continue
            if old is None or now-old['time'] > 30:
                old = {'cpu': cpu, 'memory': row['memory_mb'], 'count': 0, 'time': now}
            ready = old['count'] >= 6
            elapsed = max(.001, now-old['time'])
            growth = (row['memory_mb']-old['memory'])/elapsed
            spike = ready and cpu >= 80 and cpu-old['cpu'] >= 50 and cpu >= max(1, old['cpu'])*2
            observe(identity+':cpu', spike,
                    {'cpu_percent_one_core': cpu, 'baseline_cpu': round(old['cpu'], 2), 'warmup_samples': old['count']},
                    'process_cpu_spike', identity, row['name'])
            observe(identity+':memory', ready and growth >= 32 and system['memory_percent'] >= 85,
                    {'rss_mb': row['memory_mb'], 'growth_mb_s': round(growth, 2), 'system_memory_percent': system['memory_percent']},
                    'process_memory_growth', identity, row['name'])
            # Freeze baseline during a spike so persistent deviations do not train themselves away.
            self.profiles[identity] = {'cpu': old['cpu'] if spike else .2*cpu+.8*old['cpu'],
                                      'memory': row['memory_mb'], 'count': old['count']+1, 'time': now}
        self.profiles = {k:v for k,v in self.profiles.items() if k in live}
        for key in list(self.active):
            if key not in present:
                state = self.active.pop(key)
                if state['incident']:
                    new.append(dict(id=state['incident'],timestamp=now,phase='process_exited',kind='lifecycle',evidence={}))
        self.events.extend(new)
        return {'events': list(reversed(self.events)), 'new_events': new,
                'active_count': sum(bool(v['incident']) for v in self.active.values()),
                'trained_processes': sum(v['count'] >= 6 for v in self.profiles.values()),
                'policy': '6 warmup samples; 2 consecutive triggers; 3 clear samples to recover'}
