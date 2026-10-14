import os
import time
from fastapi.testclient import TestClient
from barg.system_monitor import SystemMonitor
from barg.backend import create_app


def test_reads_actual_process_without_synthetic_metrics():
    monitor = SystemMonitor()
    first = monitor.collect()
    own = next(r for r in first['processes'] if r['pid']==os.getpid())
    assert own['memory_mb'] > 0 and own['cpu'] is None
    second = monitor.collect()
    own = next(r for r in second['processes'] if r['pid']==os.getpid())
    assert own['cpu'] is not None and own['cpu'] >= 0
    assert own['source']=='system-psutil'
    assert 'score' not in own and 'syscalls' not in own
    assert second['alerts']==[] and second['decisions']==[]


def test_default_is_real_read_only_and_exports_are_separate(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        deadline=time.monotonic()+10
        while True:
            state=client.get('/api/status').json()
            if state.get('system'): break
            assert time.monotonic()<deadline
            time.sleep(.05)
        assert state['mode']=='system' and state['source']=='system-psutil'
        assert any(r['pid']==os.getpid() for r in state['processes'])
        for endpoint in ('/api/demo/anomaly','/api/restore'):
            assert client.post(endpoint).status_code==403
        records=client.get('/api/export/telemetry').json()
        assert records and all(r['source']=='system-psutil' for r in records)
        assert (tmp_path/'system.sqlite3').exists()
        assert not (tmp_path/'history.sqlite3').exists()
