"""Reproducible Linux matrix; simulator results are exported separately."""
import argparse
import csv
import json
import os
import platform
import random
import signal
import subprocess
import sys
import time
from pathlib import Path
from barg.simulator import simulate, trace
from barg.store import Store
from barg.profiler import fairness


def detection_metrics(rows, labels, started, completed):
    rows = [r for r in rows if not r.get('training') and started <= r['timestamp'] <= completed]
    tp=fp=tn=fn=0
    detections=[]
    recoveries=[]
    for row in rows:
        if row.get('training') or not started <= row['timestamp'] <= completed: continue
        actual=any(x['start']<=row['timestamp']<x['end'] for x in labels)
        predicted=row['status']=='ANOMALOUS'
        tp += actual and predicted
        fp += not actual and predicted
        tn += not actual and not predicted
        fn += actual and not predicted
    for label in labels:
        found=[r['timestamp'] for r in rows if label['start']<=r['timestamp']<label['end'] and r['status']=='ANOMALOUS']
        detections.append((min(found)-label['start'])*1000 if found else None)
        recovered=[r['timestamp'] for r in rows if label['end']<=r['timestamp']<=completed and r['status']=='NORMAL']
        recoveries.append((min(recovered)-label['end'])*1000 if found and recovered else None)
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'false_positive_rate':fp/(fp+tn) if fp+tn else None,
            'detection_latency_ms':detections,'recovery_ms':recoveries}


def export(results, output, title, xkey, ykey):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    (output/'results.json').write_text(json.dumps(results,indent=2))
    with (output/'results.csv').open('w',newline='') as f:
        fields=sorted(set().union(*(r.keys() for r in results)))
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in results: writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
    os.environ.setdefault('MPLCONFIGDIR',str(output.resolve()/'.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,4.5))
    positions = list(range(len(results)))
    ax.bar(positions,[r[ykey] for r in results],color='#087f70')
    ax.set_xticks(positions, [str(r[xkey]) + (f" #{r['repeat']+1}" if 'repeat' in r else '') for r in results])
    ax.set(title=title,ylabel=ykey)
    ax.tick_params(axis='x',labelrotation=25)
    fig.tight_layout()
    fig.savefig(output/'comparison.png',dpi=160)
    plt.close(fig)
    (output/'SUMMARY.md').write_text(f'# {title}\n\n{len(results)} measured records. See results.csv and results.json for individual runs.\n\nNo simulator ratio represents a Linux page-cache hit rate. Missing values are not zero. No improvement or causality is asserted without repeated controlled comparisons.\n')


def linux_matrix(root, output, repeats=3, duration=40, require_ebpf=True):
    if platform.system()!='Linux' or os.geteuid()!=0: raise RuntimeError('Linux experiments require root in the designated Ubuntu VM')
    from barg.locking import acquire
    with acquire('/run/barg') as lease:
        return _linux_matrix(root, output, repeats, duration, require_ebpf, lease)


def _linux_matrix(root, output, repeats, duration, require_ebpf, lease):
    if not 1<=repeats<=10 or not 30<=duration<=120: raise ValueError('Use 1–10 repeats and 30–120 seconds')
    from barg.control import CgroupActuator
    from barg.collector import capabilities
    guard=CgroupActuator(root,'/run/barg/rollback.json')
    if guard.original: guard.restore()
    for group in ('worker','competitor'):
        guard.read(group)
        if (guard.path(group)/'cgroup.procs').read_text().strip():
            raise RuntimeError('Experiment sandbox must be empty before starting')
    import pwd
    uid=int(os.environ.get('SUDO_UID','65534'))
    gid=pwd.getpwuid(uid).pw_gid
    if uid==0: raise RuntimeError('Launch via sudo from an ordinary user so workloads can drop root')
    output=Path(output).resolve()
    if (output/'partial.json').exists() or (output/'results.json').exists():
        raise RuntimeError('Output already contains a matrix; choose a new --output directory')
    output.mkdir(parents=True,exist_ok=True)
    workspace=output/'workloads'
    workspace.mkdir(exist_ok=True)
    os.chown(workspace,uid,gid)
    schedule=[(mode,kind,repeat) for repeat in range(repeats) for kind in ('cpu','memory','io','anomaly') for mode in ('vanilla','monitor','cpu','memory','full')]
    random.Random(42).shuffle(schedule)
    results=[]
    published=Path('data/experiments.json')
    published.parent.mkdir(parents=True,exist_ok=True)
    prior=json.loads(published.read_text()) if published.exists() else []
    for mode,kind,repeat in schedule:
        run_dir=output/f'{kind}-{mode}-{repeat}'
        run_dir.mkdir(exist_ok=False)
        agent=None
        competitor=None
        child=None
        log=(run_dir/'agent.log').open('w')
        cpu=min(os.sched_getaffinity(0))
        def join(group):
            def enter():
                Path(root,group,'cgroup.procs').write_text(str(os.getpid()))
                os.sched_setaffinity(0,{cpu})
                os.setgroups([])
                os.setgid(gid)
                os.setuid(uid)
            return enter
        def usage(group):
            return int(dict(line.split() for line in Path(root,group,'cpu.stat').read_text().splitlines())['usage_usec'])
        usage_before={g:usage(g) for g in ('worker','competitor')}
        try:
            if mode!='vanilla':
                command=[sys.executable,'-m','barg.agent','--root',root,'--groups','worker','competitor','--output',str(run_dir),'--mode',mode,'--lock-fd',str(lease.fileno())]
                if require_ebpf: command.append('--require-ebpf')
                agent=subprocess.Popen(command,stdout=log,stderr=log,pass_fds=(lease.fileno(),))
                deadline=time.monotonic()+20
                while not (run_dir/'live.json').exists():
                    if agent.poll() is not None: raise RuntimeError(f'Agent failed; inspect {run_dir}/agent.log')
                    if time.monotonic()>deadline: raise RuntimeError('Agent initialization timeout')
                    time.sleep(.2)
            competitor=subprocess.Popen([sys.executable,'-m','barg.workload','--kind','cpu','--duration',str(duration),'--directory',str(workspace)],stdout=subprocess.DEVNULL,stderr=log,preexec_fn=join('competitor'))
            child=subprocess.Popen([sys.executable,'-m','barg.workload','--kind',kind,'--duration',str(duration),'--directory',str(workspace)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,preexec_fn=join('worker'))
            try:
                stdout,stderr=child.communicate(timeout=duration+15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate()
                raise RuntimeError('Workload exceeded its time limit')
            if child.returncode: raise RuntimeError(stderr)
            workload=json.loads(stdout)
            if agent and agent.poll() is not None: raise RuntimeError('Agent exited during workload; run invalid')
            time.sleep(1.2)
        finally:
            try:
                for process in (child, competitor):
                    if process and process.poll() is None:
                        process.terminate()
                        try: process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
            finally:
                try:
                    if agent and agent.poll() is None:
                        agent.send_signal(signal.SIGTERM)
                        try: agent.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            agent.kill()
                            agent.wait()
                    if agent:
                        CgroupActuator(root,'/run/barg/rollback.json').restore()
                finally:
                    log.close()
        if agent and agent.returncode != 0:
            raise RuntimeError(f'Agent did not shut down cleanly; run invalid. Inspect {run_dir}/agent.log')
        if competitor and competitor.returncode != 0:
            raise RuntimeError(f'Competitor failed; run invalid. Inspect {run_dir}/agent.log')
        cpu_usage={g:usage(g)-usage_before[g] for g in ('worker','competitor')}
        telemetry=[]
        decisions=[]
        if mode!='vanilla':
            db=Store(run_dir/'agent.sqlite3')
            telemetry=[r for r in db.read('telemetry',10000) if r['group']=='worker']
            decisions=db.read('decision',10000)
            db.close()
        accounting=json.loads((run_dir/'live.json').read_text()).get('agent_accounting',{}) if mode!='vanilla' else {}
        all_events=sum(r.get('event_count',0) for r in telemetry)
        result={**workload,'mode':mode,'repeat':repeat,'source':'real Linux experiment','kernel':platform.release(),
                'cpu_affinity':[cpu],'cpu_usage_usec':cpu_usage,'jain_cpu_fairness':fairness(list(cpu_usage.values())),
                'agent_cpu_core_percent':100*accounting.get('cpu_seconds',0)/accounting['elapsed_seconds'] if accounting else 0,
                'agent_peak_rss_mb':accounting.get('peak_rss_mb',0),'event_processing_rate':all_events/workload['duration_s'],
                'kernel_drops':max((r.get('drops',0) for r in telemetry),default=0),
                'sequence_truncated':sum(r.get('sequence_truncated',0) for r in telemetry),
                'event_to_decision_latency_ms':sum(((r.get('event_latency_ms') or 0)+r['processing_ms'])*r.get('event_count',0) for r in telemetry)/all_events if all_events else None,
                'capabilities':capabilities(),'resource_changes':sum(bool(d['changes']) for d in decisions),
                'processing_latency_ms':sum(r['processing_ms'] for r in telemetry)/len(telemetry) if telemetry else None,
                'mean_pressure':sum(r['pressure'] for r in telemetry)/len(telemetry) if telemetry else None,
                'mean_faults_per_second':sum(r['faults'] for r in telemetry)/len(telemetry) if telemetry else None,
                'detection':detection_metrics(telemetry,workload['labels'],workload['started'],workload['completed']),
                'unavailable':{'systemwide_overhead':'Agent CPU/RSS excludes kernel BPF cost and dashboard; compare workload throughput against vanilla',
                               'compilation/sysbench/stress-ng':'Not included in bounded built-in suite'}}
        results.append(result)
        temporary=published.with_suffix('.tmp')
        temporary.write_text(json.dumps((prior+results)[-500:],indent=2))
        temporary.replace(published)
        (output/'partial.json').write_text(json.dumps(results,indent=2))
        print(f'{len(results)}/{len(schedule)} {kind} {mode}: {workload["throughput_ops_s"]:.2f} ops/s',flush=True)
    for kind in ('cpu','memory','io','anomaly'):
        export([r for r in results if r['kind']==kind],output/kind,f'Real Linux {kind} throughput; randomized repeated trials','mode','throughput_ops_s')
    (output/'results.json').write_text(json.dumps(results,indent=2))
    (output/'SUMMARY.md').write_text('# Real Linux experiment matrix\n\nSee each workload subdirectory for CSV, JSON, PNG and Markdown exports. Compare modes within a workload; do not compare raw operations across workload kinds. Raw agent logs and databases remain in per-trial directories.\n')
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--linux',action='store_true')
    p.add_argument('--root',default='/sys/fs/cgroup/barg-lab')
    p.add_argument('--output',default='results/simulator')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--duration',type=float,default=40)
    args=p.parse_args()
    if args.linux: linux_matrix(args.root,args.output,args.repeats,args.duration)
    else:
        results=[simulate(trace(),8,policy) for policy in ('FIFO','LRU','LRU-K','BARG')]
        export(results,args.output,'Synthetic page-reference simulation · seed 42 · 8 frames','policy','hit_ratio')
        print(json.dumps(results,indent=2))


if __name__=='__main__': main()
