import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Cpu,
  Database,
  Layers,
  Download,
  Shield,
  Sliders,
  FlaskConical,
  Settings,
  List,
} from "lucide-react";
export type SystemSnapshot = {
  timestamp: number;
  error: string | null;
  stale: boolean;
  collector: string;
  security?: {
    active_count: number;
    trained_processes: number;
    policy: string;
    events: {
      id: string;
      timestamp: number;
      phase: string;
      kind: string;
      name?: string;
      evidence: Record<string, number>;
    }[];
  };
  guards?: {
    identity: string;
    pid: number;
    timestamp: number;
    status: string;
    stale: boolean;
    priority_reduced: boolean;
    events: { timestamp: number; action: string; detail?: string }[];
  }[];
  system?: {
    cpu_percent: number;
    logical_cpus: number;
    memory_percent: number;
    memory_total_mb: number;
    memory_available_mb: number;
    process_count: number;
    access_denied: number;
    collection_seconds: number;
  };
  processes: {
    identity: string;
    pid: number;
    name: string;
    status: string;
    cpu: number | null;
    memory_mb: number;
    io_bytes: number | null;
    threads: number;
  }[];
};
type Point = { timestamp: number; cpu: number; memory: number; count: number };
const fmt = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: d });
const pages = [
  "Overview",
  "Processes",
  "CPU analytics",
  "Memory analytics",
  "Security",
  "Feedback engine",
  "Experiments",
  "Settings",
];
const icons = [
  Activity,
  List,
  Cpu,
  Database,
  Shield,
  Sliders,
  FlaskConical,
  Settings,
];
const descriptions = [
  "Your computer at a glance, with recent resource trends.",
  "Find a running process and inspect its current resource use.",
  "Compare processor demand and identify the busiest processes.",
  "Understand physical RAM use and the largest resident processes.",
  "Inspect resource observations. These are not malware verdicts.",
  "Review resource incidents, guarded responses and current recommendations.",
  "Record a real observation window and export its measurements.",
  "Choose how this browser displays and interprets live readings.",
];
function download(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Chart({
  points,
  field,
  label,
}: {
  points: Point[];
  field: "cpu" | "memory";
  label: string;
}) {
  return (
    <div className="sys-chart">
      <div className="sys-chart-label">
        <strong>{label}</strong>
        <span>0–100%</span>
      </div>
      {points.length < 2 ? (
        <p>Collecting trend data — two fresh readings are needed.</p>
      ) : (
        <svg
          viewBox="0 0 600 140"
          role="img"
          aria-label={`${label}, last ${points.length} samples`}
        >
          <path
            d="M0 10H600 M0 70H600 M0 130H600"
            stroke="#e1ece8"
            fill="none"
          />
          <polyline
            points={points
              .map(
                (p, i) =>
                  `${(i / (points.length - 1)) * 600},${130 - Math.min(100, Math.max(0, p[field])) * 1.2}`,
              )
              .join(" ")}
            fill="none"
            stroke="#008575"
            strokeWidth="3"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      )}
      <small>
        {points.length
          ? new Date(points[0].timestamp * 1000).toLocaleTimeString()
          : ""}{" "}
        · {points.length} unique samples · browser session
      </small>
    </div>
  );
}
export default function SystemMonitor({
  snapshot,
  connected,
}: {
  snapshot: SystemSnapshot;
  connected: boolean;
}) {
  const [page, setPage] = useState("Overview"),
    [query, setQuery] = useState(""),
    [sort, setSort] = useState("cpu"),
    [selected, setSelected] = useState<string | null>(null),
    [limit, setLimit] = useState(50);
  const [prefs, setPrefs] = useState(() => {
    try {
      const p = JSON.parse(localStorage.getItem("barg-display") || "{}");
      return {
        cpu: Number(p.cpu) >= 1 && Number(p.cpu) <= 1000 ? Number(p.cpu) : 80,
        memory:
          Number(p.memory) >= 1 && Number(p.memory) <= 100
            ? Number(p.memory)
            : 85,
        history: [30, 60, 120].includes(p.history) ? p.history : 60,
        compact: !!p.compact,
      };
    } catch {
      return { cpu: 80, memory: 85, history: 60, compact: false };
    }
  });
  const [history, setHistory] = useState<Point[]>([]),
    [recording, setRecording] = useState(false),
    [duration, setDuration] = useState(60),
    [samples, setSamples] = useState<Point[]>([]),
    [elapsed, setElapsed] = useState(0);
  const start = useRef(0),
    last = useRef(0),
    [paused, setPaused] = useState(false),
    [held, setHeld] = useState<SystemSnapshot | null>(null);
  useEffect(() => {
    localStorage.setItem("barg-display", JSON.stringify(prefs));
  }, [prefs]);
  useEffect(() => {
    if (
      !snapshot.system ||
      snapshot.stale ||
      snapshot.error ||
      !connected ||
      snapshot.timestamp === last.current
    )
      return;
    last.current = snapshot.timestamp;
    const p = {
      timestamp: snapshot.timestamp,
      cpu: snapshot.system.cpu_percent,
      memory: snapshot.system.memory_percent,
      count: snapshot.system.process_count,
    };
    setHistory((h) => [...h, p].slice(-prefs.history));
    if (recording && Date.now() - start.current <= duration * 1000)
      setSamples((s) => [...s, p]);
  }, [snapshot.timestamp, recording, prefs.history, connected]);
  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(() => {
      const seconds = (Date.now() - start.current) / 1000;
      setElapsed(Math.min(seconds, duration));
      if (seconds >= duration) setRecording(false);
    }, 250);
    return () => clearInterval(timer);
  }, [recording, duration]);
  const view = paused && held && page === "Processes" ? held : snapshot,
    s = view.system,
    detail = view.processes.find((p) => p.identity === selected);
  const byCpu = [...view.processes].sort(
      (a, b) => (b.cpu ?? -1) - (a.cpu ?? -1),
    ),
    byMemory = [...view.processes].sort((a, b) => b.memory_mb - a.memory_mb);
  const rows = view.processes
    .filter((p) =>
      (p.name + " " + p.pid).toLowerCase().includes(query.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "memory"
        ? b.memory_mb - a.memory_mb
        : sort === "name"
          ? a.name.localeCompare(b.name)
          : sort === "threads"
            ? b.threads - a.threads
            : (b.cpu ?? -1) - (a.cpu ?? -1),
    );
  const observations = view.processes.filter((p) => (p.cpu ?? 0) >= prefs.cpu);
  const metric = (label: string, value: string, unit: string) => (
    <div className="stat" key={label}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        <span>{unit}</span>
      </div>
    </div>
  );
  const bars = (kind: "cpu" | "memory") => (
    <section className="panel">
      <h2>
        {kind === "cpu" ? "Highest CPU demand" : "Largest resident processes"}
      </h2>
      <p>
        {kind === "cpu"
          ? "Percent of one logical core; can exceed 100%."
          : "RSS in MiB; shared pages can appear in multiple processes."}
      </p>
      <div className="sys-bars">
        {(kind === "cpu" ? byCpu : byMemory).slice(0, 8).map((p) => {
          const value = kind === "cpu" ? p.cpu : p.memory_mb;
          const max =
            kind === "cpu"
              ? Math.max(100, byCpu[0]?.cpu ?? 0)
              : Math.max(1, byMemory[0]?.memory_mb ?? 1);
          return (
            <button
              key={p.identity}
              onClick={() => {
                setSelected(p.identity);
                setPage("Processes");
              }}
            >
              <span>
                {p.name}
                <small>PID {p.pid}</small>
              </span>
              <strong>
                {fmt(value)} {kind === "cpu" ? "%" : "MiB"}
              </strong>
              <i style={{ width: `${((value ?? 0) / max) * 100}%` }} />
            </button>
          );
        })}
      </div>
    </section>
  );
  return (
    <div className={`shell ${prefs.compact ? "sys-compact" : ""}`}>
      <aside>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Overview");
          }}
        >
          <span className="brandmark">
            <Layers />
          </span>
          <span>
            BARG<small>RESOURCE GOVERNANCE</small>
          </span>
        </a>
        <div className="nav-label">SYSTEM MONITOR</div>
        <nav aria-label="Main navigation">
          {pages.map((p, i) => {
            const Icon = icons[i];
            return (
              <button
                key={p}
                className={page === p ? "active" : ""}
                aria-current={page === p ? "page" : undefined}
                onClick={() => {
                  setPage(p);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                <Icon size={18} />
                {p}
              </button>
            );
          })}
        </nav>
      </aside>
      <main>
        <header>
          <span>Workspace / {page}</span>
          <span>
            {connected ? "Stream connected" : "Reconnecting"} ·{" "}
            {new Date(view.timestamp * 1000).toLocaleTimeString()}
          </span>
        </header>
        <div className="content system-content">
          <div className="heading">
            <div>
              <div className="eyebrow">CURRENT COMPUTER READINGS</div>
              <h1>{page === "Overview" ? "System overview" : page}</h1>
              <p>{descriptions[pages.indexOf(page)]}</p>
            </div>
            <a
              className="button secondary"
              href="/api/export/telemetry?format=csv"
              download
            >
              <Download size={16} />
              Export readings
            </a>
          </div>
          <div className="mode-banner live">
            <Activity size={18} />
            <strong>LIVE SYSTEM MONITOR</strong>
            <span>
              {view.collector} · Read-only ·{" "}
              {paused ? "Process display paused" : "Continuous sampling"}
            </span>
          </div>
          {(!connected || snapshot.stale || snapshot.error) && (
            <div className="error" role="alert">
              {snapshot.error ||
                "Waiting for fresh readings. Displayed data may be stale."}
            </div>
          )}
          {page === "Overview" && (
            <>
              <div className="stats">
                {metric("SYSTEM CPU", fmt(s?.cpu_percent), "% all cores")}
                {metric("MEMORY USED", fmt(s?.memory_percent), "%")}
                {metric(
                  "AVAILABLE RAM",
                  fmt(s ? s.memory_available_mb / 1024 : null),
                  "GiB",
                )}
                {metric("PROCESSES", fmt(s?.process_count, 0), "readable")}
              </div>
              <div className="sys-grid">
                <section className="panel">
                  <Chart points={history} field="cpu" label="CPU activity" />
                </section>
                <section className="panel">
                  <Chart points={history} field="memory" label="Memory use" />
                </section>
                {bars("cpu")}
                <section className="panel">
                  <h2>Monitoring health</h2>
                  <dl className="sys-facts">
                    <dt>Logical processors</dt>
                    <dd>{s?.logical_cpus ?? "—"}</dd>
                    <dt>Last collection duration</dt>
                    <dd>{fmt(s?.collection_seconds)} seconds</dd>
                    <dt>Protected processes skipped</dt>
                    <dd>{s?.access_denied ?? "—"}</dd>
                    <dt>Data source</dt>
                    <dd>{view.collector}</dd>
                  </dl>
                  <p>
                    Only accessible processes are listed. Trends begin when this
                    browser connects.
                  </p>
                </section>
              </div>
            </>
          )}
          {page === "Processes" && (
            <section className="panel">
              <div className="sys-toolbar">
                <input
                  aria-label="Search processes"
                  placeholder="Search name or PID"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setLimit(50);
                  }}
                />
                <select
                  aria-label="Sort processes"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="cpu">Highest CPU</option>
                  <option value="memory">Largest memory</option>
                  <option value="name">Name A–Z</option>
                  <option value="threads">Most threads</option>
                </select>
                <button
                  className="button secondary"
                  onClick={() => {
                    setHeld(snapshot);
                    setPaused(!paused);
                  }}
                >
                  {paused ? "Resume display" : "Pause display"}
                </button>
                <span>{rows.length} matches</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {[
                        "Process / PID",
                        "CPU per core",
                        "RAM MiB",
                        "I/O KiB/s",
                        "Threads",
                        "State",
                      ].map((t) => (
                        <th key={t}>{t}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, limit).map((p) => (
                      <tr key={p.identity}>
                        <td>
                          <button
                            className="sys-link"
                            onClick={() => setSelected(p.identity)}
                          >
                            {p.name}
                          </button>
                          <small className="sys-sub">PID {p.pid}</small>
                        </td>
                        <td>{fmt(p.cpu)}%</td>
                        <td>{fmt(p.memory_mb)}</td>
                        <td>
                          {fmt(p.io_bytes == null ? null : p.io_bytes / 1024)}
                        </td>
                        <td>{p.threads}</td>
                        <td>
                          <span className="badge">{p.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!rows.length && <p>No matching processes.</p>}
              {rows.length > limit && (
                <button
                  className="button secondary"
                  onClick={() => setLimit(limit + 50)}
                >
                  Show 50 more
                </button>
              )}
              {selected && (
                <div className="sys-detail">
                  <h2>
                    {detail
                      ? `${detail.name} · PID ${detail.pid}`
                      : "Process no longer present"}
                  </h2>
                  {detail && (
                    <dl className="sys-facts">
                      <dt>CPU / one core</dt>
                      <dd>{fmt(detail.cpu)}%</dd>
                      <dt>Resident memory</dt>
                      <dd>{fmt(detail.memory_mb)} MiB</dd>
                      <dt>Threads</dt>
                      <dd>{detail.threads}</dd>
                      <dt>Process identity</dt>
                      <dd>{detail.identity}</dd>
                    </dl>
                  )}
                  <p>
                    New processes need two readings for rates. A dash means
                    unavailable.
                  </p>
                  <button
                    className="button secondary"
                    onClick={() => setSelected(null)}
                  >
                    Close details
                  </button>
                </div>
              )}
            </section>
          )}
          {page === "CPU analytics" && (
            <>
              <div className="stats">
                {metric("TOTAL CPU", fmt(s?.cpu_percent), "% all cores")}
                {metric("LOGICAL CORES", fmt(s?.logical_cpus, 0), "cores")}
                {metric("BUSIEST PROCESS", fmt(byCpu[0]?.cpu), "% one core")}
                {metric(
                  "TOTAL THREADS",
                  fmt(
                    view.processes.reduce((n, p) => n + p.threads, 0),
                    0,
                  ),
                  "readable",
                )}
              </div>
              <div className="sys-grid">
                <section className="panel">
                  <Chart points={history} field="cpu" label="Total CPU trend" />
                  <p>
                    System CPU is normalized across all cores. Process usage is
                    measured against one core.
                  </p>
                </section>
                {bars("cpu")}
              </div>
            </>
          )}
          {page === "Memory analytics" && (
            <>
              <div className="stats">
                {metric(
                  "PHYSICAL RAM",
                  fmt(s ? s.memory_total_mb / 1024 : null),
                  "GiB",
                )}
                {metric(
                  "USED RAM",
                  fmt(
                    s
                      ? (s.memory_total_mb - s.memory_available_mb) / 1024
                      : null,
                  ),
                  "GiB",
                )}
                {metric(
                  "AVAILABLE",
                  fmt(s ? s.memory_available_mb / 1024 : null),
                  "GiB",
                )}
                {metric("UTILIZATION", fmt(s?.memory_percent), "%")}
              </div>
              <div className="sys-grid">
                <section className="panel">
                  <Chart
                    points={history}
                    field="memory"
                    label="Physical memory trend"
                  />
                  <p>
                    Available RAM includes reclaimable memory. Process RSS
                    totals are not the same as physical memory usage because
                    pages may be shared.
                  </p>
                </section>
                {bars("memory")}
              </div>
            </>
          )}
          {(page === "Security" || page === "Feedback engine") && (
            <section className="panel sys-gap" style={{ marginBottom: 24 }}>
              <h2>Resource incident response</h2>
              <p>Detect → confirm → respond within scope → observe recovery.</p>
              <div className="stats">
                {metric(
                  "ACTIVE INCIDENTS",
                  String(snapshot.security?.active_count ?? 0),
                  "confirmed",
                )}
                {metric(
                  "BASELINES READY",
                  String(snapshot.security?.trained_processes ?? 0),
                  "processes",
                )}
              </div>
              <p>
                {snapshot.security?.policy ??
                  "Waiting for detector. Restart the backend after this update."}
              </p>
              <p>
                CPU spikes require a learned baseline, at least 80% of one core,
                a 50-point jump and twice baseline. System CPU/RAM pressure
                triggers at 90%. Rapid memory growth requires at least 32 MiB/s
                and system memory ≥85%. Resource events are not malware
                verdicts.
              </p>
              <h3>Managed workload stabilization</h3>
              <p>Run a chosen workload from the project terminal using:</p>
              <pre
                style={{ whiteSpace: "pre-wrap" }}
              >{String.raw`.\.venv\Scripts\python.exe -m barg.guard -- python your_workload.py`}</pre>
              <p>
                The supervisor lowers only its directly launched workload to
                below-normal priority after three readings with process CPU ≥80%
                and system CPU ≥85%. It restores after 20 seconds, with a
                30-second cooldown. No memory deletion, suspension or process
                termination is performed.
              </p>
              {!snapshot.guards?.length && (
                <p>
                  No guarded workload registered. Detection is active; automatic
                  priority response requires launching a workload with the
                  supervisor.
                </p>
              )}
              {snapshot.guards?.map((g) => (
                <div className="sys-detail" key={g.identity}>
                  <h3>
                    PID {g.pid} ·{" "}
                    {g.stale ? "Supervisor heartbeat stale" : g.status}
                  </h3>
                  <p>
                    {g.stale
                      ? "Response state cannot be verified. Check the supervisor terminal and process priority."
                      : g.priority_reduced
                        ? "Priority relief lease active"
                        : "No priority relief lease active"}
                  </p>
                  {g.events.slice(0, 5).map((e, i) => (
                    <p key={i}>
                      {new Date(e.timestamp * 1000).toLocaleTimeString()} ·{" "}
                      {e.action} {e.detail}
                    </p>
                  ))}
                </div>
              ))}
              <h3>Incident timeline</h3>
              <a
                className="button secondary"
                href="/api/export/anomaly?format=csv"
                download
              >
                Export incident history
              </a>
              {!snapshot.security?.events.length && (
                <p>
                  No confirmed events in this server session. Baselines need six
                  valid readings.
                </p>
              )}
              {snapshot.security?.events.slice(0, 30).map((e, i) => (
                <div className="sys-detail" key={e.id + e.phase + i}>
                  <strong>
                    {e.kind.replaceAll("_", " ")} · {e.phase} ·{" "}
                    {e.name ?? "Process"}
                  </strong>
                  <p>{new Date(e.timestamp * 1000).toLocaleString()}</p>
                  <p>
                    {Object.entries(e.evidence)
                      .map(([k, v]) => `${k}: ${fmt(v)}`)
                      .join(" · ")}
                  </p>
                </div>
              ))}
            </section>
          )}
          {page === "Security" && (
            <>
              <div className="stats">
                {metric(
                  "HIGH CPU OBSERVATIONS",
                  String(observations.length),
                  "processes",
                )}
                {metric(
                  "PROTECTED / SKIPPED",
                  fmt(s?.access_denied, 0),
                  "processes",
                )}
              </div>
              <section className="panel">
                <h2>Resource watchlist</h2>
                <p>
                  Processes at or above {prefs.cpu}% of one core in the latest
                  reading. These observations do not establish malicious
                  behavior.
                </p>
                {observations.length ? (
                  observations.map((p) => (
                    <div className="sys-event" key={p.identity}>
                      <strong>
                        {p.name} · PID {p.pid}
                      </strong>
                      <span>{fmt(p.cpu)}% CPU</span>
                      <button
                        className="button secondary"
                        onClick={() => {
                          setSelected(p.identity);
                          setPage("Processes");
                        }}
                      >
                        Inspect
                      </button>
                    </div>
                  ))
                ) : (
                  <p>
                    No readable processes exceed your CPU observation threshold.
                  </p>
                )}
              </section>
              <section className="panel sys-gap">
                <h2>Detection coverage</h2>
                <p>
                  Available: CPU, resident memory, I/O rates, thread counts and
                  process state. Unavailable: syscall sequences, executable
                  reputation and kernel anomaly detection. No malware verdict is produced.
                  The guard supervisor can apply bounded priority relief to explicitly launched workloads.
                </p>
              </section>
            </>
          )}
          {page === "Feedback engine" && (
            <section className="panel">
              <h2>Recommendations from current readings</h2>
              <p>
                These recommendations are advisory. Guard supervisor actions are
                reported separately above.
              </p>
              <div className="sys-detail">
                <h3>Memory headroom</h3>
                <p>
                  {s
                    ? s.memory_percent >= prefs.memory
                      ? `Memory usage is ${fmt(s.memory_percent)}%, above your ${prefs.memory}% threshold. Review the largest processes before starting additional workloads.`
                      : `Memory usage is ${fmt(s.memory_percent)}%, below your ${prefs.memory}% threshold. No memory recommendation is triggered.`
                    : "Waiting for a system reading."}
                </p>
                <button
                  className="button secondary"
                  onClick={() => setPage("Memory analytics")}
                >
                  Review memory
                </button>
              </div>
              <div className="sys-detail">
                <h3>CPU demand</h3>
                <p>
                  {observations.length
                    ? `${observations.length} processes exceed your ${prefs.cpu}% per-core threshold. Inspect sustained demand across several samples before taking action.`
                    : "No process crosses the configured CPU threshold in this sample."}
                </p>
                <button
                  className="button secondary"
                  onClick={() => setPage("CPU analytics")}
                >
                  Review CPU
                </button>
              </div>
              <p>
                Linux cgroup policy enforcement requires the Ubuntu agent; this
                monitor cannot apply BARG resource allocation on Windows.
              </p>
            </section>
          )}
          {page === "Experiments" && (
            <section className="panel">
              <h2>Live observation recording</h2>
              <p>
                Capture actual system CPU, memory and process counts while you
                run your own workload. This is an observational recording, not a
                controlled BARG benchmark.
              </p>
              <div className="sys-toolbar">
                <label>
                  Duration{" "}
                  <select
                    aria-label="Recording duration"
                    value={duration}
                    disabled={recording}
                    onChange={(e) => setDuration(Number(e.target.value))}
                  >
                    <option value={30}>30 seconds</option>
                    <option value={60}>1 minute</option>
                    <option value={120}>2 minutes</option>
                  </select>
                </label>
                <button
                  className="button"
                  disabled={
                    recording ||
                    !connected ||
                    !s ||
                    snapshot.stale ||
                    !!snapshot.error
                  }
                  onClick={() => {
                    start.current = Date.now();
                    setSamples([]);
                    setElapsed(0);
                    setRecording(true);
                  }}
                >
                  Start recording
                </button>
                <button
                  className="button secondary"
                  disabled={!recording}
                  onClick={() => setRecording(false)}
                >
                  Stop recording
                </button>
                <button
                  className="button secondary"
                  disabled={!samples.length || recording}
                  onClick={() =>
                    download("barg-live-observation.json", {
                      source: "system-psutil",
                      kind: "observational",
                      elapsed_seconds: elapsed,
                      samples,
                    })
                  }
                >
                  Export recording
                </button>
              </div>
              <progress max={duration} value={elapsed} />
              <p role="status">
                {recording ? "Recording" : "Idle"} · {Math.floor(elapsed)}{" "}
                seconds · {samples.length} fresh samples collected
              </p>
              {samples.length > 0 && (
                <>
                  <div className="stats">
                    {metric(
                      "AVERAGE CPU",
                      fmt(
                        samples.reduce((n, p) => n + p.cpu, 0) / samples.length,
                      ),
                      "%",
                    )}
                    {metric(
                      "PEAK CPU",
                      fmt(Math.max(...samples.map((p) => p.cpu))),
                      "%",
                    )}
                    {metric(
                      "PEAK MEMORY",
                      fmt(Math.max(...samples.map((p) => p.memory))),
                      "%",
                    )}
                  </div>
                  <Chart
                    points={samples}
                    field="cpu"
                    label="Recorded CPU usage"
                  />
                </>
              )}
              <p>
                Recording continues across sidebar navigation. Keep this tab
                open; export before refreshing. Missing or stale samples are
                excluded.
              </p>
            </section>
          )}
          {page === "Settings" && (
            <div className="sys-grid">
              <section className="panel sys-settings">
                <h2>Display and observation preferences</h2>
                <label>
                  CPU watch threshold (% of one core)
                  <input
                    type="number"
                    min={1}
                    max={1000}
                    value={prefs.cpu}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        cpu: Math.min(
                          1000,
                          Math.max(1, Number(e.target.value)),
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Memory recommendation threshold (%)
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={prefs.memory}
                    onChange={(e) =>
                      setPrefs({
                        ...prefs,
                        memory: Math.min(
                          100,
                          Math.max(1, Number(e.target.value)),
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  Trend history
                  <select
                    value={prefs.history}
                    onChange={(e) =>
                      setPrefs({ ...prefs, history: Number(e.target.value) })
                    }
                  >
                    <option value={30}>30 samples</option>
                    <option value={60}>60 samples</option>
                    <option value={120}>120 samples</option>
                  </select>
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={prefs.compact}
                    onChange={(e) =>
                      setPrefs({ ...prefs, compact: e.target.checked })
                    }
                  />{" "}
                  Compact process table
                </label>
                <p>
                  Saved automatically in this browser. These settings affect
                  display and recommendations, not OS resource limits.
                </p>
                <button
                  className="button secondary"
                  onClick={() =>
                    setPrefs({
                      cpu: 80,
                      memory: 85,
                      history: 60,
                      compact: false,
                    })
                  }
                >
                  Reset preferences
                </button>
              </section>
              <section className="panel">
                <h2>Collector information</h2>
                <dl className="sys-facts">
                  <dt>Source</dt>
                  <dd>{view.collector}</dd>
                  <dt>Last scan duration</dt>
                  <dd>{fmt(s?.collection_seconds)} seconds</dd>
                  <dt>Access</dt>
                  <dd>Read-only</dd>
                  <dt>Skipped processes</dt>
                  <dd>{s?.access_denied ?? "—"}</dd>
                </dl>
                <p>
                  The sampling interval includes collection time and the backend
                  delay. Browser display settings do not change collection
                  frequency.
                </p>
              </section>
            </div>
          )}
          <footer>
            <span>BARG · Actual host measurements</span>
            <span>
              Guarded workload response is opt-in · No command lines collected
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
