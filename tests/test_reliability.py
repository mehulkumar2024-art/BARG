import json
import time
import pytest
from fastapi.testclient import TestClient
from barg.backend import create_app
from barg.control import Controller, SimulatedActuator
from barg.engine import Engine
from barg.evaluate import detection_metrics
from barg.model import Settings
from test_control import row


@pytest.mark.parametrize('page_size', [4096, 65536])
def test_fractional_memory_target_matches_kernel_pages(page_size):
    actuator = SimulatedActuator()
    actuator.page_size = page_size
    decision = Controller(actuator).decide(row(status='NORMAL', memory_mb=13.123),
        Settings(monitoring_only=False, memory_enabled=True), now=0)
    value = decision['after']['memory.low']
    assert value > 0 and value % page_size == 0
    assert value <= 13.123 * .25 * 1024**2


def test_restore_clears_pending_outcomes_and_updates_visible_allocations():
    engine = Engine(Settings(training_windows=5, monitoring_only=False, cpu_enabled=True))
    for _ in range(6): engine.demo()
    assert engine.controller.pending
    engine.restore()
    assert not engine.controller.pending and not engine.controller.last
    assert all(r['cpu_weight'] == 100 and r['memory_low'] == 0 for r in engine.rows.values())


def test_demo_windows_session_and_freshness():
    first, second = Engine(), Engine()
    assert first.snapshot()['timestamp'] == 0
    first.demo()
    second.demo()
    assert set(first.rows).isdisjoint(second.rows)
    stamp = first.snapshot()['timestamp']
    assert first.snapshot()['timestamp'] == stamp
    first.inject_until = first.tick + 20
    labels = [first.demo()[1][0]['label'] for _ in range(21)]
    assert labels == [True] * 20 + [False]


@pytest.mark.parametrize('payload', ['{broken', '[]', '{"timestamp": "bad"}'])
def test_invalid_live_snapshot_is_visible_error_not_failed_stream(tmp_path, payload):
    (tmp_path/'live.json').write_text(payload)
    with TestClient(create_app(tmp_path, 'live')) as client:
        result = client.get('/api/status').json()
        assert result['error'] and result['stale']
        with client.websocket_connect('/ws') as ws:
            assert ws.receive_json()['processes'] == []


def test_valid_idle_live_heartbeat_and_missing_producer(tmp_path):
    snapshot = Engine().snapshot()
    snapshot['timestamp'] = time.time()
    (tmp_path/'live.json').write_text(json.dumps(snapshot))
    with TestClient(create_app(tmp_path, 'live')) as client:
        result = client.get('/api/status').json()
        assert not result['error'] and not result['stale']


def test_live_bridge_accepts_complete_profile_rows(tmp_path):
    engine = Engine()
    engine.demo()
    snapshot = engine.snapshot()
    for row in snapshot['processes']: row['source'] = 'linux-ebpf'
    snapshot.update(source='linux-ebpf', collector='eBPF attached')
    (tmp_path/'live.json').write_text(json.dumps(snapshot))
    with TestClient(create_app(tmp_path, 'live')) as client:
        result = client.get('/api/status').json()
        assert not result['error'] and len(result['processes']) == 3
        assert result['processes'][0]['cpu_weight'] == 100


@pytest.mark.parametrize('payload', ['{broken', '{}', '[1]'])
def test_corrupt_experiment_handoff_has_actionable_response(tmp_path, payload):
    (tmp_path/'experiments.json').write_text(payload)
    with TestClient(create_app(tmp_path, 'demo')) as client:
        for endpoint in ('/api/experiments', '/api/export/experiment'):
            response = client.get(endpoint)
            assert response.status_code == 503
            assert 'Experiment results unavailable' in response.json()['detail']


def test_training_windows_do_not_count_as_detection_or_recovery():
    rows = [dict(timestamp=2, training=True, status='ANOMALOUS'),
            dict(timestamp=4, training=False, status='NORMAL')]
    result = detection_metrics(rows, [dict(start=1, end=3)], 1, 5)
    assert result['detection_latency_ms'] == [None]
    assert result['recovery_ms'] == [None]
    assert result['tp'] == 0


def test_demo_storage_error_does_not_kill_update_task(tmp_path, monkeypatch):
    from barg.store import Store
    import sqlite3
    def failed_add(*args): raise sqlite3.OperationalError('disk unavailable')
    monkeypatch.setattr(Store, 'add', failed_add)
    with TestClient(create_app(tmp_path, 'demo')) as client:
        result = client.get('/api/status').json()
        assert result['error'] == 'disk unavailable'
        assert len(result['processes']) == 3
