import pytest
from barg.control import SimulatedActuator,Controller,CgroupActuator
from barg.model import Settings
from barg.engine import Engine
from test_algorithms import sample


def row(**kw):
    data=dict(group='worker',identity='42:100',timestamp=1,source='simulated',cpu=20,pressure=10,
              score=.9,status='ANOMALOUS',classification='CPU-bound',memory_mb=100)
    data.update(kw)
    return data


def test_monitor_never_writes():
    actuator=SimulatedActuator()
    result=Controller(actuator).decide(row(),Settings(),now=0)
    assert result['changes']=={}
    assert actuator.original=={}


def test_cooldown_bounds_and_restoration():
    actuator=SimulatedActuator()
    controller=Controller(actuator)
    settings=Settings(monitoring_only=False,cpu_enabled=True,memory_enabled=True,anomaly_response=True)
    assert controller.decide(row(),settings,now=0)['after']['cpu.weight']==80
    assert controller.decide(row(),settings,now=1)['changes']=={}
    for t in range(5,100,5):controller.decide(row(),settings,now=t)
    assert actuator.read('worker')['cpu.weight']==50
    actuator.restore()
    assert actuator.read('worker')=={'cpu.weight':100,'memory.low':0}


def test_memory_budget_and_anomaly_conflict():
    actuator=SimulatedActuator()
    controller=Controller(actuator)
    settings=Settings(monitoring_only=False,memory_enabled=True,anomaly_response=True)
    for t in range(0,100,5):controller.decide(row(status='NORMAL',memory_mb=1000),settings,now=t)
    assert actuator.read('worker')['memory.low']==64*1024**2
    assert controller.decide(row(),settings,now=100)['after']['memory.low']==56*1024**2


def test_scope_guard():
    with pytest.raises(ValueError): CgroupActuator('/sys/fs/cgroup','/tmp/journal')
    actuator=object.__new__(CgroupActuator)
    from pathlib import Path
    actuator.root=Path('/tmp/barg-root').resolve()
    for group in ('../system','a/b','..','a\\b',''):
        with pytest.raises(ValueError):actuator.path(group)


def test_file_adapter_rollback(tmp_path):
    # Test cgroup file operations against temporary regular files, never host controls.
    actuator=object.__new__(CgroupActuator)
    actuator.root=tmp_path
    actuator.journal=tmp_path/'rollback.json'
    actuator.original={}
    leaf=tmp_path/'worker'
    leaf.mkdir()
    (leaf/'cpu.weight').write_text('100')
    (leaf/'memory.low').write_text('0')
    assert actuator.apply('worker',{'cpu.weight':80})['cpu.weight']==80
    assert actuator.journal.exists()
    actuator.restore()
    assert (leaf/'cpu.weight').read_text()=='100'
    assert not actuator.journal.exists()
    with pytest.raises(ValueError):actuator.apply('worker',{'cpu.weight':49})


def test_feedback_pid_reuse_and_event_flow():
    engine=Engine(Settings(training_windows=5))
    for _ in range(5):engine.ingest(sample())
    assert not engine.profiles['42:100'].windows==0
    row1,decision=engine.ingest(sample(identity='42:200'))
    assert '42:100' not in engine.profiles
    assert row1['training']
    assert len(engine.decisions)==6
    assert decision['identity']=='42:200'


def test_demo_detection_flow():
    engine=Engine(Settings(training_windows=5))
    for _ in range(6):engine.demo()
    engine.inject_until=engine.tick+10
    for _ in range(6):engine.demo()
    assert any(a['status']=='ANOMALOUS' for a in engine.alerts)


def test_pressure_rollback_bypasses_cooldown():
    actuator=SimulatedActuator()
    controller=Controller(actuator)
    settings=Settings(monitoring_only=False,cpu_enabled=True,anomaly_response=True)
    controller.decide(row(pressure=0),settings,now=0)
    result=controller.decide(row(pressure=30),settings,now=1)
    assert result['after']['cpu.weight']==100
    assert result['reason'].startswith('rollback')


def test_no_actuation_during_training():
    controller=Controller(SimulatedActuator())
    settings=Settings(monitoring_only=False,cpu_enabled=True,anomaly_response=True)
    assert controller.decide(row(training=True),settings,now=0)['changes']=={}
