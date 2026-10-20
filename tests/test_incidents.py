from barg.incidents import IncidentDetector
from barg.guard import PriorityLease


def snapshot(t, cpu=10, memory=100, pressure=20):
    return dict(timestamp=t,system={'cpu_percent':pressure,'memory_percent':50},
                processes=[dict(identity='10:1',name='work',cpu=cpu,memory_mb=memory)])


def test_spike_confirmation_recovery_and_no_baseline_poisoning():
    d=IncidentDetector()
    for t in range(1,8): assert not d.update(snapshot(t))['events']
    assert not d.update(snapshot(8,95))['events']
    result=d.update(snapshot(9,95)); assert result['active_count']==1
    assert result['new_events'][0]['kind']=='process_cpu_spike'
    for t in range(10,20): assert d.update(snapshot(t,95))['active_count']==1
    for t in (20,21): assert d.update(snapshot(t))['active_count']==1
    result=d.update(snapshot(22)); assert result['active_count']==0
    assert result['new_events'][0]['phase']=='recovered'


def test_exit_and_system_pressure():
    d=IncidentDetector()
    d.update(snapshot(1,pressure=95))
    assert d.update(snapshot(2,pressure=95))['active_count']==1
    for t in range(3,10): d.update(snapshot(t))
    d.update(snapshot(10,99)); d.update(snapshot(11,99))
    s=snapshot(12); s['processes']=[]
    assert any(e['phase']=='process_exited' for e in d.update(s)['new_events'])
    assert not d.profiles


class Process:
    def __init__(self): self.priority=32; self.writes=[]
    def nice(self,value=None):
        if value is not None: self.priority=value;self.writes.append(value)
        return self.priority


def test_lease_threshold_expiry_cooldown_and_restore():
    p=Process(); lease=PriorityLease(p,32,16384)
    for t in range(3): lease.step(95,40,t)
    assert not p.writes
    for t in range(3,6): lease.step(95,90,t)
    assert p.writes==[16384]
    lease.step(95,90,25); assert p.writes==[16384,32]
    for t in range(26,55): lease.step(95,90,t)
    assert p.writes==[16384,32]
    lease.step(95,90,55); assert p.writes[-1]==16384
    lease.restore(56); assert p.writes[-1]==32


def test_does_not_override_external_priority_change():
    p=Process(); lease=PriorityLease(p,32,16384)
    for t in range(3): lease.step(95,90,t)
    p.priority=64
    lease.restore(10)
    assert p.priority==64
    assert lease.events[-1]['action']=='external_priority_change'
