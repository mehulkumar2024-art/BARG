"""Windows-only bounded responsiveness lab; never targets existing processes."""
import argparse
import csv
import json
import multiprocessing as mp
import platform
import random
import statistics
import time
import uuid
from pathlib import Path
import psutil


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1)*fraction
    lo = int(index)
    return ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(index-lo)


def worker(role, core, duration, ready, go, stop, output):
    try:
        process = psutil.Process()
        process.cpu_affinity([core])
        process.nice(psutil.NORMAL_PRIORITY_CLASS)
        ready.set()
        if not go.wait(15):
            raise RuntimeError('Start barrier timed out')
        start = time.perf_counter()
        operations = 0
        latencies = []
        deadline = start
        while not stop.is_set() and time.perf_counter()-start < duration:
            if role == 'foreground':
                # Response includes wakeup delay and fixed computation, not just service time.
                time.sleep(max(0, deadline-time.perf_counter()))
                for i in range(25000):
                    operations += (i*i)%97
                now = time.perf_counter()
                latency = (now-deadline)*1000
                latencies.append(latency)
                output.put({'sample': latency})
                deadline = max(deadline+.05, now)  # No unbounded backlog.
            else:
                for i in range(10000):
                    operations += 1
                    _ = (i*i)%97
        output.put({'result': {'role': role, 'elapsed_s': time.perf_counter()-start,
                              'operations': operations, 'latencies_ms': latencies}})
    except Exception as exc:
        ready.set()
        output.put({'error': str(exc)})


def trial(mode, duration, core, target_ms):
    import queue
    ctx = mp.get_context('spawn')
    go, stop = ctx.Event(), ctx.Event()
    outputs = [ctx.Queue(), ctx.Queue()]
    ready = [ctx.Event(), ctx.Event()]
    children = [ctx.Process(target=worker,args=(role,core,duration,ready[i],go,stop,outputs[i]))
                for i,role in enumerate(('foreground','background'))]
    events=[]; samples=[]; results={}; reduced=False; original=None; background=None
    parent_start=time.process_time(); high=0
    try:
        for child in children: child.start()
        if not all(e.wait(15) for e in ready): raise RuntimeError('Worker setup timed out')
        background=psutil.Process(children[1].pid)
        original=background.nice()
        background.cpu_percent(None)
        go.set(); started=time.monotonic(); last=started; previous_samples=0
        while len(results)<2 and time.monotonic()-started < duration+5:
            for i,q in enumerate(outputs):
                while True:
                    try: message=q.get_nowait()
                    except queue.Empty: break
                    if 'error' in message: raise RuntimeError(message['error'])
                    if 'sample' in message: samples.append(message['sample'])
                    if 'result' in message: results[i]=message['result']
            now=time.monotonic()
            if mode != 'baseline' and now-last >= .5 and background.is_running():
                cpu=background.cpu_percent(None)
                window=samples[previous_samples:]; previous_samples=len(samples)
                p95=percentile(window,.95)
                high=high+1 if p95 is not None and p95>target_ms and cpu>=20 else 0
                events.append({'seconds':now-started,'action':'observe','background_cpu':cpu,'p95_ms':p95})
                if mode=='adaptive' and high>=2 and not reduced:
                    background.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); reduced=True
                    events.append({'seconds':now-started,'action':'priority_lowered','reason':'Two latency windows above target with competing CPU demand'})
                last=now
            time.sleep(.02)
        if len(results)!=2: raise RuntimeError('Incomplete worker output; trial invalid')
    finally:
        # Restore while the owned worker is alive; an exited process has no remaining priority.
        if reduced and background:
            try:
                if background.is_running() and background.nice()==psutil.BELOW_NORMAL_PRIORITY_CLASS:
                    background.nice(original); events.append({'action':'priority_restored'})
                else: events.append({'action':'worker_exited_or_priority_changed'})
            except psutil.NoSuchProcess: events.append({'action':'worker_exited'})
            except psutil.Error as exc:
                events.append({'action':'restore_failed_worker_cleanup_required','error':str(exc)})
        stop.set()
        for child in children:
            if child.pid is not None:
                child.join(2)
                if child.is_alive(): child.terminate(); child.join(2)
        for q in outputs: q.close()
    latencies=results[0]['latencies_ms']
    if not latencies: raise RuntimeError('No latency samples')
    return {'mode':mode,'samples':len(latencies),'p50_ms':percentile(latencies,.5),
            'p95_ms':percentile(latencies,.95),'max_ms':max(latencies),
            'deadline_miss_fraction':sum(v>target_ms for v in latencies)/len(latencies),
            'background_ops_s':results[1]['operations']/results[1]['elapsed_s'],
            'supervisor_cpu_s':time.process_time()-parent_start,'interventions':int(reduced),
            'latencies_ms':latencies,'events':events}


def run(duration=8,repeats=3,target_ms=20,data_dir='data',seed=42):
    if platform.system()!='Windows': raise RuntimeError('This lab uses Windows priorities. Use barg.evaluate --linux for cgroup experiments.')
    if not 4<=duration<=30 or not 2<=repeats<=5 or not 1<=target_ms<=100: raise ValueError('Use duration 4–30s, repeats 2–5, latency target 1–100ms')
    directory=Path(data_dir); directory.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents multiple labs competing with each other.
    lock=directory/'responsiveness.lock'
    handle=lock.open('x')
    try:
        run_id=uuid.uuid4().hex; output=directory/'responsiveness'/run_id; output.mkdir(parents=True)
        core=psutil.Process().cpu_affinity()[-1]
        schedule=[(mode,r) for r in range(repeats) for mode in ('baseline','monitor','adaptive')]
        random.Random(seed).shuffle(schedule)
        report={'id':run_id,'status':'running','platform':platform.platform(),'core':core,'duration_s':duration,
                'repeats':repeats,'target_ms':target_ms,'seed':seed,'trials':[], 'summary':[],
                'scope':'Real Windows one-core contention experiment. Owned workers only. Not the production guard policy or Linux cgroup evaluation.',
                'limitations':'Fixed synthetic workload; uncontrolled host load; short trials; no causal or general performance guarantee.'}
        def save():
            report['updated_at']=time.time()
            (output/'report.json').write_text(json.dumps(report,indent=2))
            temporary=directory/'responsiveness.tmp'
            temporary.write_text(json.dumps(report));temporary.replace(directory/'responsiveness.json')
        save()
        try:
            for mode,repeat in schedule:
                row=trial(mode,duration,core,target_ms);row['repeat']=repeat+1;report['trials'].append(row);save()
                print(f'{mode} #{repeat+1}: p95={row["p95_ms"]:.2f}ms; actions={row["interventions"]}',flush=True)
            for mode in ('baseline','monitor','adaptive'):
                rows=[r for r in report['trials'] if r['mode']==mode]
                report['summary'].append({'mode':mode,**{k:statistics.median(r[k] for r in rows) for k in ('p50_ms','p95_ms','background_ops_s','deadline_miss_fraction','supervisor_cpu_s')},
                    'p95_min_ms':min(r['p95_ms'] for r in rows),'p95_max_ms':max(r['p95_ms'] for r in rows),
                    'interventions':sum(r['interventions'] for r in rows)})
            report['status']='completed';save()
            fields=['mode','repeat','p50_ms','p95_ms','max_ms','deadline_miss_fraction','background_ops_s','supervisor_cpu_s','interventions']
            with (output/'trials.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(report['trials'])
            print('Report:',output/'report.json')
            return report
        except BaseException as exc:
            report['status']='failed';report['error']=str(exc) or type(exc).__name__;save();raise
    finally:
        handle.close();lock.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--duration',type=float,default=8);p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--target-ms',type=float,default=20);p.add_argument('--data-dir',default='data')
    a=p.parse_args();run(a.duration,a.repeats,a.target_ms,a.data_dir)
if __name__=='__main__': main()
