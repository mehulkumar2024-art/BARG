import pytest
from barg.responsiveness import percentile, run
from barg.backend import create_app
from fastapi.testclient import TestClient
import json

def test_percentiles_include_interpolation_and_empty():
    assert percentile([], .95) is None
    assert percentile([10, 0, 20], .5) == 10
    assert percentile([0, 100], .95) == 95

def test_report_endpoint_missing_and_saved(tmp_path):
    with TestClient(create_app(tmp_path,'demo')) as client:
        assert client.get('/api/experiments/responsiveness').json()['status']=='not_started'
        (tmp_path/'responsiveness.json').write_text(json.dumps({'status':'completed','trials':[],'summary':[]}))
        assert client.get('/api/experiments/responsiveness').json()['status']=='completed'
        (tmp_path/'responsiveness.json').write_text('{')
        assert client.get('/api/experiments/responsiveness').status_code==503

def test_invalid_bounds_do_not_create_lock(tmp_path,monkeypatch):
    monkeypatch.setattr('barg.responsiveness.platform.system',lambda:'Windows')
    with pytest.raises(ValueError): run(duration=100,data_dir=tmp_path)
    assert not (tmp_path/'responsiveness.lock').exists()
