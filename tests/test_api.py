from fastapi.testclient import TestClient
from barg.backend import create_app
from barg.model import Settings
import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.mark.parametrize('port', [8000, 8080, 9000])
def test_custom_port_stream_and_controls(tmp_path, port):
    origin = f'http://127.0.0.1:{port}'
    with TestClient(create_app(tmp_path, 'demo'), base_url=origin) as client:
        with client.websocket_connect(f'ws://127.0.0.1:{port}/ws', headers={'origin':origin}) as ws:
            assert len(ws.receive_json()['processes']) == 3
        assert client.post('/api/demo/anomaly', headers={'origin':origin}).status_code == 200
        assert client.post('/api/restore', headers={'origin':'https://evil.invalid'}).status_code == 403
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f'ws://127.0.0.1:{port}/ws', headers={'origin':'https://evil.invalid'}):
                pass


def test_api_stream_settings_simulator_and_export(tmp_path):
    app=create_app(tmp_path, 'demo')
    with TestClient(app) as client:
        assert client.get('/api/status').status_code==200
        with client.websocket_connect('/ws') as ws:
            message=ws.receive_json()
            assert message['source']=='simulated'
            assert len(message['processes'])==3
            identity=message['processes'][0]['identity']
        assert client.get('/api/processes/'+identity).json()['history']
        assert client.put('/api/settings',json={'alpha':0}).status_code==422
        settings=Settings(monitoring_only=False,cpu_enabled=True).model_dump()
        assert client.put('/api/settings',json=settings).status_code==200
        assert client.post('/api/demo/anomaly').status_code==200
        assert client.post('/api/restore').status_code==200
        assert client.get('/api/settings').json()['monitoring_only']
        result=client.post('/api/experiments/simulator',json={'frames':8,'length':500,'seed':42})
        assert result.status_code==200 and len(result.json())==4
        assert 'synthetic' in result.json()[0]['source']
        assert client.get('/api/export/simulator?format=csv').headers['content-type'].startswith('text/csv')
        assert client.post('/api/processes/'+identity+'/retrain').status_code==200
        assert client.put('/api/settings',json=settings,headers={'Origin':'https://evil.invalid'}).status_code==403


def test_live_web_service_cannot_actuate(tmp_path):
    with TestClient(create_app(tmp_path,'live')) as client:
        assert client.post('/api/restore').status_code==403
        assert client.post('/api/demo/anomaly').status_code==403
        assert client.put('/api/settings',json=Settings().model_dump()).status_code==403


def test_root_agent_experiments_are_read_without_database_writes(tmp_path):
    import json
    record={'mode':'monitor','source':'real Linux experiment','throughput_ops_s':12.5}
    (tmp_path/'experiments.json').write_text(json.dumps([record]))
    with TestClient(create_app(tmp_path, 'demo')) as client:
        assert client.get('/api/experiments').json()['linux']==[record]
        assert client.get('/api/export/experiment').json()==[record]
