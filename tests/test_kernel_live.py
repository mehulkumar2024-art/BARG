"""Opt-in, real Ubuntu checks. Run only in the explicitly prepared BARG VM."""
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
import pytest

pytestmark=pytest.mark.skipif(platform.system()!='Linux' or os.environ.get('BARG_KERNEL_TESTS')!='1',
                            reason='Opt-in Ubuntu kernel test: set BARG_KERNEL_TESTS=1 after preparing the sandbox')


@pytest.fixture(autouse=True)
def exclusive_sandbox():
    import fcntl
    with Path('/run/barg/agent.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def test_real_tracepoint_attachment_and_reception():
    from barg.collector import Collector
    from barg.control import CgroupActuator
    actuator=CgroupActuator('/sys/fs/cgroup/barg-lab','/run/barg/rollback.json')
    leaf=actuator.path('worker')
    assert not (leaf/'cgroup.procs').read_text().strip(),'Sandbox must be empty'
    collector=Collector(actuator.root,['worker'],require_ebpf=True)
    child=None
    try:
        child=subprocess.Popen([sys.executable,'-m','barg.launch','--kind','cpu','--duration','5'],stdout=subprocess.DEVNULL)
        samples=[]
        deadline=time.monotonic()+7
        while time.monotonic()<deadline and child.poll() is None:
            samples.extend(collector.collect(.5))
        assert collector.events>0,'Attachment without event reception is insufficient'
        assert any(s.source=='linux-ebpf' and s.syscall_count>0 for s in samples)
        assert any(s.switches>0 for s in samples)
    finally:
        if child and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        collector.close()


def test_real_cgroup_readback_and_restore():
    from barg.control import CgroupActuator
    actuator=CgroupActuator('/sys/fs/cgroup/barg-lab','/run/barg/rollback.json')
    assert not (actuator.path('worker')/'cgroup.procs').read_text().strip()
    before=actuator.read('worker')
    try:
        after=actuator.apply('worker',{'cpu.weight':80,'memory.low':8*1024**2})
        assert after['cpu.weight']==80 and after['memory.low']==8*1024**2
    finally: actuator.restore()
    assert actuator.read('worker')==before
