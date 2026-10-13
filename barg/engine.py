import math
import random
import time
from collections import deque
from barg.model import Sample, Settings
from barg.profiler import Profile, fairness
from barg.control import Controller, SimulatedActuator


class Engine:
    def __init__(self, settings=None, actuator=None):
        self.settings = settings or Settings()
        self.profiles = {}
        self.rows = {}
        self.decisions = deque(maxlen=500)
        self.alerts = deque(maxlen=500)
        self.controller = Controller(actuator or SimulatedActuator())
        self.tick = 0
        self.rng = random.Random(42)
        self.inject_until = 0

    def ingest(self, sample):
        started = time.perf_counter()
        # Identity is PID:starttime (Linux) or an explicit demo generation.
        for identity in list(self.rows):
            if sample.timestamp-self.rows[identity]['timestamp'] > 60 or (self.rows[identity]['pid']==sample.pid and identity!=sample.identity):
                self.rows.pop(identity)
                self.profiles.pop(identity, None)
        if sample.identity not in self.profiles and len(self.profiles) >= 512:
            oldest = min(self.rows, key=lambda k:self.rows[k]['timestamp'])
            self.rows.pop(oldest)
            self.profiles.pop(oldest)
        profile = self.profiles.setdefault(sample.identity, Profile(self.settings))
        previous = profile.state
        row = profile.update(sample, self.settings)
        self.rows[sample.identity] = row
        fair = fairness([r['cpu'] for r in self.rows.values()])
        decision = self.controller.decide(row, self.settings, fair)
        row['cpu_weight'] = decision['after']['cpu.weight']
        row['memory_low'] = decision['after']['memory.low']
        row['processing_ms'] = (time.perf_counter()-started)*1000
        self.decisions.append(decision)
        if row['status'] != previous:
            self.alerts.append({'timestamp':sample.timestamp,'identity':sample.identity,'status':row['status'],
                                'score':row['score'],'components':row['components'],'threshold':self.settings.threshold,
                                'confidence':row['confidence'],'response':decision['reason'],'source':sample.source})
        return row, decision

    def demo(self):
        self.tick += 1
        rows = []
        for i,name in enumerate(('matrix-worker','file-worker','memory-worker')):
            anomaly = i==1 and self.tick < self.inject_until
            cpu = 85 if anomaly else 25+i*12+5*math.sin(self.tick/5+i)
            burst = 22 if anomaly else 2+i*2+self.rng.random()
            calls = [257,1,87,257,1,1,87]*100 if anomaly else [0,1,202,35,0,202]*40
            sample = Sample(identity=f'{4100+i}:demo-1',pid=4100+i,name=name,group=name,timestamp=time.time(),
                source='simulated',cpu=cpu,burst_ms=burst,switches=int(cpu*3),faults=220 if anomaly else 8+i*4,
                memory_mb=80+i*48,pressure=15 if anomaly else i*3,io_bytes=2e6 if anomaly else 4096,
                syscalls=calls,syscall_count=len(calls),label=anomaly)
            rows.append(self.ingest(sample))
        return rows

    def snapshot(self):
        rows = list(self.rows.values())
        return {'timestamp':time.time(),'source': rows[0]['source'] if rows else 'unavailable',
                'processes':rows,'alerts':list(self.alerts),'decisions':list(self.decisions)[-60:],
                'fairness':fairness([r['cpu'] for r in rows]),'settings':self.settings.model_dump()}
