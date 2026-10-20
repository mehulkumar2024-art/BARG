import asyncio
import csv
import io
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ConfigDict
from barg.engine import Engine
from barg.model import Settings, Sample
from barg.store import Store, read_records
from barg.simulator import simulate, trace


def trusted_origin(origin, request_url):
    if origin is None:
        return True
    if origin in ('http://127.0.0.1:5173', 'http://localhost:5173'):
        return True
    try:
        source, target = urlsplit(origin), urlsplit(str(request_url))
        scheme = {'ws': 'http', 'wss': 'https'}.get(target.scheme, target.scheme)
        return (source.scheme == scheme and source.hostname in ('127.0.0.1', 'localhost')
                and source.hostname == target.hostname
                and (source.port or (443 if source.scheme == 'https' else 80)) == (target.port or (443 if scheme == 'https' else 80))
                and not source.username and not source.password and not source.path
                and not source.query and not source.fragment)
    except ValueError:
        return False


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frames: int = Field(8, ge=1, le=128)
    length: int = Field(5000, ge=100, le=100000)
    seed: int = Field(42, ge=0, le=2**32-1)


class LiveRow(Sample):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    score: float = Field(ge=0, le=1)
    status: str
    training: bool
    prediction: float | None
    ewma: float
    cpu_weight: int
    distribution: dict[str, float]


class LiveSnapshot(BaseModel):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    timestamp: float = Field(ge=0)
    source: str
    processes: list[LiveRow]
    alerts: list[dict]
    decisions: list[dict]
    fairness: float = Field(ge=0, le=1)
    settings: Settings


def create_app(data_dir='data', mode='system'):
    if mode not in ('demo','live','system'):
        raise ValueError('Mode must be system, demo or live')
    directory = Path(data_dir)
    engine = Engine()
    state = {'snapshot':engine.snapshot(), 'error':None}

    @asynccontextmanager
    async def lifespan(app):
        store = Store(directory/('system.sqlite3' if mode=='system' else 'history.sqlite3'))
        app.state.store = store
        if mode == 'system':
            from barg.system_monitor import SystemMonitor
            monitor = SystemMonitor()
            from barg.incidents import IncidentDetector
            detector = IncidentDetector()
        async def update():
            while True:
                try:
                    if mode == 'demo':
                        previous_alert=engine.alerts[-1] if engine.alerts else None
                        for row,decision in engine.demo():
                            store.add('telemetry',row['timestamp'],row)
                            store.add('decision',row['timestamp'],decision)
                        new_alerts=list(engine.alerts)
                        start=new_alerts.index(previous_alert)+1 if previous_alert in new_alerts else 0
                        for alert in new_alerts[start:]: store.add('anomaly',alert['timestamp'],alert)
                        state['snapshot'] = engine.snapshot()
                    elif mode == 'system':
                        state['snapshot'] = await asyncio.to_thread(monitor.collect)
                        state['snapshot']['settings'] = engine.settings.model_dump()
                        incidents = detector.update(state['snapshot'])
                        for event in incidents.pop('new_events'):
                            store.add('anomaly', event['timestamp'], event)
                        state['snapshot']['security'] = incidents
                        state['snapshot']['alerts'] = incidents['events']
                        store.add_batch('telemetry', state['snapshot']['processes'])
                    else:
                        # Read-only bridge. The root agent never executes browser requests.
                        state['snapshot'] = LiveSnapshot.model_validate_json((directory/'live.json').read_text()).model_dump()
                    state['error'] = None
                except (OSError, ValueError, sqlite3.Error) as exc:
                    state['error'] = str(exc)
                await asyncio.sleep(engine.settings.interval)
        task = asyncio.create_task(update())
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        engine.controller.actuator.restore()
        store.close()

    app = FastAPI(title='BARG Resource Governance', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver'])
    app.state.engine = engine

    @app.middleware('http')
    async def local_mutations(request: Request, call_next):
        origin = request.headers.get('origin')
        if request.method not in ('GET','HEAD','OPTIONS') and not trusted_origin(origin, request.url):
            return Response('Untrusted origin',status_code=403)
        return await call_next(request)

    def snapshot():
        result = engine.snapshot() if mode=='demo' else state['snapshot'].copy()
        result['mode'] = mode
        if mode == 'system':
            guards = []
            for path in sorted(directory.glob('guard-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                try:
                    if path.stat().st_size > 100000: continue
                    guard = json.loads(path.read_text(encoding='utf-8'))
                    guard['stale'] = time.time()-float(guard['timestamp']) > 5
                    guards.append(guard)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
            result['guards'] = guards
        result['collector'] = 'SIMULATED' if mode=='demo' else result.get('collector','unavailable')
        result['error'] = state['error']
        result['stale'] = time.time()-result['timestamp'] > max(5, result['settings']['interval']*3, result.get('system',{}).get('collection_seconds',0)*3)
        result['live_controls_readonly'] = mode!='demo'
        return result

    def demo_only():
        if mode != 'demo':
            raise HTTPException(403,'Live control is configured in the local root agent CLI, never through the web service')

    @app.get('/api/status')
    async def status(): return snapshot()

    @app.get('/api/processes')
    async def processes(): return snapshot()['processes']

    @app.get('/api/processes/{identity}')
    async def detail(identity: str):
        if mode == 'demo' and identity in engine.profiles:
            return {'current':engine.rows[identity],'history':list(engine.profiles[identity].history)}
        rows = [r for r in snapshot()['processes'] if r['identity']==identity]
        if not rows: raise HTTPException(404,'Process identity not found')
        database = 'system.sqlite3' if mode=='system' else 'agent.sqlite3'
        return {'current':rows[0],'history':list(reversed([r for r in read_records(directory/database,'telemetry',10000) if r['identity']==identity][:120]))}

    @app.post('/api/processes/{identity}/retrain')
    async def retrain(identity: str):
        demo_only()
        if identity not in engine.profiles: raise HTTPException(404,'Process not found')
        from barg.profiler import Profile
        engine.restore()
        engine.profiles[identity] = Profile(engine.settings)
        engine.rows[identity].update(training=True, status='TRAINING')
        return {'training':True}

    @app.get('/api/settings')
    async def get_settings(): return snapshot()['settings']

    @app.put('/api/settings')
    async def settings(value: Settings):
        demo_only()
        if value.monitoring_only or (engine.settings.cpu_enabled and not value.cpu_enabled) or (engine.settings.memory_enabled and not value.memory_enabled):
            engine.restore()
        engine.settings = value
        return value

    @app.post('/api/restore')
    async def restore():
        demo_only()
        engine.settings.monitoring_only = True
        return engine.restore()

    @app.post('/api/demo/anomaly')
    async def anomaly():
        demo_only()
        engine.inject_until = engine.tick+20
        return {'source':'simulated','duration_windows':20}

    @app.get('/api/anomalies')
    async def anomalies(): return snapshot()['alerts']

    @app.get('/api/decisions')
    async def decisions(): return snapshot()['decisions']

    @app.post('/api/experiments/simulator')
    async def simulator(config: SimulationRequest):
        refs = trace(config.seed,config.length)
        results = await asyncio.to_thread(lambda:[simulate(refs,config.frames,p) for p in ('FIFO','LRU','LRU-K','BARG')])
        app.state.store.add('simulator',time.time(),{'config':config.model_dump(),'results':results})
        return results

    @app.get('/api/experiments')
    async def experiments():
        return {'simulator':app.state.store.read('simulator'), 'linux':experiment_records()}

    def experiment_records():
        path = directory/'experiments.json'
        try:
            records = json.loads(path.read_text()) if path.exists() else []
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
                raise ValueError('Expected a list of experiment records')
            return records
        except (OSError, ValueError) as exc:
            raise HTTPException(503, f'Experiment results unavailable: {exc}') from exc

    @app.get('/api/export/{kind}')
    async def export(kind: str, format: str='json'):
        if kind not in ('telemetry','decision','anomaly','simulator','experiment'): raise HTTPException(404,'Unknown dataset')
        records = read_records(directory/'agent.sqlite3',kind,10000) if mode=='live' and kind in ('telemetry','decision','anomaly') else app.state.store.read(kind,10000)
        if kind=='experiment':
            records=experiment_records()
        if format == 'json': return records
        if format != 'csv': raise HTTPException(422,'Use json or csv')
        buf = io.StringIO()
        if records:
            writer = csv.DictWriter(buf,fieldnames=sorted(set().union(*(r.keys() for r in records))))
            writer.writeheader()
            for row in records: writer.writerow({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})
        return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="barg-{kind}.csv"'})

    @app.websocket('/ws')
    async def stream(websocket: WebSocket):
        if not trusted_origin(websocket.headers.get('origin'), websocket.url):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(snapshot())
                await asyncio.sleep(engine.settings.interval)
        except (WebSocketDisconnect, RuntimeError): pass

    dist = Path(__file__).resolve().parent.parent/'frontend'/'dist'
    if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='dashboard')
    else:
        @app.get('/')
        async def unbuilt_dashboard():
            return Response('Dashboard has not been built. Run scripts/setup.ps1 on Windows or scripts/setup.sh on Ubuntu, then restart the backend. API documentation: /docs', status_code=503, media_type='text/plain')
    return app


app = create_app(os.environ.get('BARG_DATA','data'),os.environ.get('BARG_MODE','system'))
