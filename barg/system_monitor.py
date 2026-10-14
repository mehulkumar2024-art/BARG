"""Read-only host process monitoring. No synthetic samples or resource writes."""
import platform
import time
import psutil


class SystemMonitor:
    def __init__(self):
        self.previous = {}
        psutil.cpu_percent(interval=None)

    def collect(self):
        started = time.monotonic()
        current = {}
        rows = []
        denied = 0
        for process in psutil.process_iter():
            if process.pid == 0:
                continue  # Windows idle pseudo-process is unused CPU, not workload usage.
            try:
                with process.oneshot():
                    identity = f'{process.pid}:{process.create_time():.6f}'
                    name = process.name()
                    status = process.status()
                    cpu_time = process.cpu_times()
                    memory = process.memory_info()
                    threads = process.num_threads()
                    try:
                        io = process.io_counters()
                        io_bytes = io.read_bytes + io.write_bytes
                    except (psutil.Error, AttributeError, NotImplementedError):
                        io_bytes = None
                    ticks = cpu_time.user + cpu_time.system
                    stamp = time.monotonic()
                    previous = self.previous.get(identity)
                    elapsed = stamp - previous[0] if previous else None
                    cpu = max(0, (ticks-previous[1])/elapsed*100) if elapsed and elapsed > 0 else None
                    rate = max(0, (io_bytes-previous[2])/elapsed) if elapsed and elapsed > 0 and io_bytes is not None and previous[2] is not None else None
                    current[identity] = (stamp, ticks, io_bytes)
                    rows.append(dict(identity=identity, pid=process.pid, name=name, status=status,
                                     cpu=cpu, memory_mb=memory.rss/1024**2, io_bytes=rate,
                                     threads=threads, timestamp=time.time(), source='system-psutil'))
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                continue
            except psutil.AccessDenied:
                denied += 1
        self.previous = current
        memory = psutil.virtual_memory()
        rows.sort(key=lambda r: (r['cpu'] or 0, r['memory_mb']), reverse=True)
        return dict(timestamp=time.time(), source='system-psutil', collector=f'{platform.system()} / psutil',
                    processes=rows, alerts=[], decisions=[], fairness=None,
                    system=dict(cpu_percent=psutil.cpu_percent(interval=None), logical_cpus=psutil.cpu_count(),
                                memory_percent=memory.percent, memory_total_mb=memory.total/1024**2,
                                memory_available_mb=memory.available/1024**2,
                                process_count=len(rows), access_denied=denied,
                                collection_seconds=time.monotonic()-started),
                    unavailable=['CPU burst tracing', 'Syscall sequences', 'Memory PSI',
                                 'BARG anomaly scores', 'Linux cgroup allocation'])
