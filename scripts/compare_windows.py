"""Repeated measured userspace throughput. Does not claim kernel governance gains."""
import json, random, subprocess, sys, statistics, platform
from pathlib import Path

def main():
    schedule=[(kind,mode,repeat) for kind in ('cpu','memory','io') for mode in ('baseline','guarded') for repeat in range(3)]
    random.Random(42).shuffle(schedule)
    rows=[]
    root=Path('results/windows-comparison'); root.mkdir(parents=True,exist_ok=True)
    for kind,mode,repeat in schedule:
        workload=[sys.executable,'-m','barg.workload','--kind',kind,'--duration','2','--memory-mb','8']
        command=([sys.executable,'-m','barg.guard','--data-dir',str(root/'guards'),'--']+workload) if mode=='guarded' else workload
        result=subprocess.run(command,capture_output=True,text=True,timeout=20,check=True)
        record=json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
        rows.append(dict(record,mode=mode,repeat=repeat))
    summaries={}
    for kind in ('cpu','memory','io'):
        summaries[kind]={mode:statistics.median(r['throughput_ops_s'] for r in rows if r['kind']==kind and r['mode']==mode) for mode in ('baseline','guarded')}
    events=[e for p in (root/'guards').glob('*.json') for e in json.loads(p.read_text())['events']]
    payload=dict(platform=platform.platform(),scope='Short Windows userspace throughput comparison, not Linux BARG validation. Concurrent host load is uncontrolled. No guaranteed response activation.',rows=rows,median_throughput=summaries,guard_actions=events)
    (root/'results.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps({'median_throughput':summaries,'guard_actions':len(events),'trials':len(rows)},indent=2))
if __name__=='__main__': main()
