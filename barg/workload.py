"""Bounded disposable workloads. No arbitrary command or user-file input."""
import argparse
import hashlib
import json
import random
import tempfile
import time
from pathlib import Path


def run(kind='cpu', duration=5, memory_mb=32, directory='data/workloads'):
    if kind not in ('cpu','memory','io','anomaly') or not .1 <= duration <= 120 or not 1 <= memory_mb <= 128:
        raise ValueError('Workload bounds: 0.1–120 seconds; 1–128 MiB')
    root = Path(directory).resolve()
    root.mkdir(parents=True,exist_ok=True)
    rng = random.Random(42)
    start = time.perf_counter()
    wall_start = time.time()
    operations = 0
    block = b'barg-disposable-benchmark\n'*128
    allocation = bytearray(memory_mb*1024**2) if kind=='memory' else None
    intervals = []
    if kind=='anomaly': intervals=[{'start':wall_start+duration*.5,'end':wall_start+duration*.75,'anomalous':True}]
    with tempfile.TemporaryDirectory(prefix='barg-',dir=root) as scratch:
        while time.perf_counter()-start < duration:
            elapsed = time.perf_counter()-start
            if kind=='cpu':
                for _ in range(1000): hashlib.sha256(block).digest()
                operations += 1000
            elif kind=='memory':
                for _ in range(1000): allocation[rng.randrange(len(allocation))] = operations%256
                operations += 1000
            elif kind=='io' or (kind=='anomaly' and duration*.5<=elapsed<duration*.75):
                # Only 16 private disposable files; bounded disk footprint below 64 KiB.
                path = Path(scratch)/f'block-{operations%16}.dat'
                path.write_bytes(block)
                path.read_bytes()
                operations += 1
                if kind=='io': time.sleep(.002)
            else:
                hashlib.sha256(block).digest()
                operations += 1
                time.sleep(.01)
    elapsed = time.perf_counter()-start
    return {'kind':kind,'source':'measured userspace workload','started':wall_start,'completed':time.time(),
            'duration_s':elapsed,'operations':operations,'throughput_ops_s':operations/elapsed,
            'memory_limit_mb':memory_mb,'disk_bound_bytes':16*len(block),'labels':intervals}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--kind',choices=['cpu','memory','io','anomaly'],default='cpu')
    p.add_argument('--duration',type=float,default=5)
    p.add_argument('--memory-mb',type=int,default=32)
    p.add_argument('--directory',default='data/workloads')
    args=p.parse_args()
    print(json.dumps(run(args.kind,args.duration,args.memory_mb,args.directory)))


if __name__=='__main__': main()
