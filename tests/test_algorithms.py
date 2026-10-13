import pytest
from barg.profiler import EWMA,Ngrams,divergence,zscore,fairness,Profile
from barg.simulator import simulate,trace
from barg.model import Sample,Settings


def sample(**kwargs):
    data=dict(identity='42:100',pid=42,name='worker',group='worker',timestamp=1,source='simulated',cpu=20,
              burst_ms=2,switches=10,faults=2,memory_mb=20,pressure=0,syscalls=[0,1,0,1]*100,io_bytes=100)
    data.update(kwargs)
    return Sample(**data)


def test_ewma_prediction_and_initialization():
    model=EWMA(.25)
    assert model.update(8)==(None,8)
    assert model.update(16)==(8,10)
    with pytest.raises(ValueError): EWMA(0)


def test_ngrams_sliding_expiry_and_cross_batch():
    n=Ngrams(4)
    n.update([1,2,3])
    n.update([4,5])
    assert n.distribution(2)=={(2,3):1/3,(3,4):1/3,(4,5):1/3}
    assert n.distribution(3)=={(2,3,4):.5,(3,4,5):.5}


def test_statistics():
    assert divergence({(1,):1},{(2,):1})==1
    assert divergence({(1,):1},{(1,):1})==0
    assert zscore(10,[10,10,10])==0
    assert zscore(20,[10,10,10])==10
    assert fairness([10,10,10])==1
    assert fairness([10,0])==.5
    assert fairness([])==1


def test_training_freeze_confirmation_and_recovery():
    settings=Settings(training_windows=5)
    profile=Profile(settings)
    for _ in range(5): assert profile.update(sample(),settings)['training']
    frozen=profile.baseline.copy()
    bad=sample(burst_ms=50,faults=500,io_bytes=100000,syscalls=[99,88,77]*500)
    profile.update(bad,settings)
    assert profile.state=='WARNING'
    profile.update(bad,settings)
    assert profile.state=='WARNING'
    assert profile.update(bad,settings)['status']=='ANOMALOUS'
    assert profile.baseline==frozen
    observed=[]
    for _ in range(20): observed.append(profile.update(sample(),settings)['status'])
    assert 'RECOVERING' in observed
    assert observed[-1]=='NORMAL'


@pytest.mark.parametrize('policy',['FIFO','LRU','LRU-K','BARG'])
def test_replacement_accounting(policy):
    result=simulate([1,2,1,3,1,2],2,policy)
    assert result['hits']+result['faults']==6
    assert result['replacements']==result['faults']-2
    assert result['hit_ratio']+result['miss_ratio']==1


def test_lru_and_lruk_known_trace():
    assert simulate([1,2,1,3,1],2,'LRU')['hits']==2
    assert simulate([1,2,1,3,1],2,'LRU-K')['hits']==2
    assert simulate([1,2,1,3,1],2,'FIFO')['hits']==1
    assert trace(42,100)==trace(42,100)
    with pytest.raises(ValueError):simulate([1],0)


def test_serialization_and_validation():
    s=sample()
    assert Sample.model_validate_json(s.model_dump_json())==s
    with pytest.raises(ValueError):sample(cpu=-1)
    with pytest.raises(ValueError):sample(cpu=float('nan'))
    with pytest.raises(ValueError):Settings(alpha=0)
