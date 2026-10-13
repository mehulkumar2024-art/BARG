import pytest
from barg.evaluate import detection_metrics
from barg.workload import run
from barg.store import Store
from barg.collector import capabilities


def test_labeled_detection_metrics():
    rows=[{'timestamp':i,'status':'ANOMALOUS' if i in (2,3) else 'NORMAL'} for i in range(5)]
    metrics=detection_metrics(rows,[{'start':1,'end':3}],0,4)
    assert metrics['tp']==1 and metrics['fp']==1 and metrics['fn']==1 and metrics['tn']==2
    assert metrics['precision']==.5 and metrics['recall']==.5
    assert metrics['detection_latency_ms']==[1000]


def test_workload_limits_and_disposable_files(tmp_path):
    result=run('io',.1,1,tmp_path)
    assert result['operations']>0
    assert result['duration_s']>=.1
    assert list(tmp_path.iterdir())==[]
    with pytest.raises(ValueError):run('io',1000,1,tmp_path)


def test_sqlite_roundtrip(tmp_path):
    store=Store(tmp_path/'db.sqlite3')
    store.add('decision',1,{'source':'simulated','changes':{'cpu.weight':80}})
    assert store.read('decision')[0]['changes']['cpu.weight']==80
    store.close()


@pytest.mark.skipif(not capabilities()['cgroups_v2'],reason='Requires Linux cgroups v2; Windows cannot verify kernel operation')
def test_linux_capability_probe():
    assert capabilities()['platform']=='Linux'
