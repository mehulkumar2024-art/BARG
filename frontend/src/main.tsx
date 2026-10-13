import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Cpu,
  Database,
  ShieldCheck,
  GitBranch,
  FlaskConical,
  Settings as SettingsIcon,
  Layers,
  ArrowUpRight,
  Radio,
  Download,
  RotateCcw,
  Play,
  ChevronRight,
} from "lucide-react";
import "./style.css";

type Row = {
  identity: string;
  pid: number;
  name: string;
  group: string;
  cpu: number;
  memory_mb: number;
  faults: number;
  syscall_count: number;
  interval_s: number;
  switches: number;
  score: number;
  status: string;
  training: boolean;
  prediction: number | null;
  ewma: number;
  burst_ms: number;
  cpu_weight: number;
  pressure: number;
  drops: number;
  sequence_truncated: number;
  distribution: Record<string, number>;
  timestamp: number;
};
type Config = {
  monitoring_only: boolean;
  cpu_enabled: boolean;
  memory_enabled: boolean;
  anomaly_response: boolean;
  alpha: number;
  threshold: number;
  interval: number;
  training_windows: number;
  cooldown: number;
};
type Decision = {
  timestamp: number;
  identity: string;
  reason: string;
  changes: Record<string, number>;
  before: Record<string, number>;
  after: Record<string, number>;
  outcome: Record<string, unknown> | null;
};
type Snapshot = {
  mode: string;
  source: string;
  collector: string;
  timestamp: number;
  stale: boolean;
  error: string | null;
  collector_error?: string | null;
  processes: Row[];
  alerts: {
    timestamp: number;
    identity: string;
    status: string;
    score: number;
    response: string;
  }[];
  decisions: Decision[];
  fairness: number;
  settings: Config;
  live_controls_readonly: boolean;
};
type Sim = {
  policy: string;
  hit_ratio: number;
  faults: number;
  hits: number;
  execution_ms: number;
  source: string;
};
type Experiment = {
  kind: string;
  mode: string;
  repeat: number;
  throughput_ops_s: number;
  agent_cpu_core_percent: number;
  agent_peak_rss_mb: number;
  jain_cpu_fairness: number;
  resource_changes: number;
  detection: {
    precision: number | null;
    recall: number | null;
    false_positive_rate: number | null;
  };
};
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
  Layers,
  Cpu,
  Database,
  ShieldCheck,
  GitBranch,
  FlaskConical,
  SettingsIcon,
];
const fmt = (v: number | undefined, d = 1) =>
  (v ?? 0).toLocaleString(undefined, { maximumFractionDigits: d });
async function api(path: string, method = "GET", body?: unknown) {
  const r = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw Error((await r.text()).slice(0, 240));
  return r.json();
}

function Chart({
  series,
  labels,
  height = 180,
}: {
  series: number[][];
  labels: string[];
  height?: number;
}) {
  const max = Math.max(1, ...series.flat());
  const colors = ["#087f70", "#409f8e", "#80bdae"];
  return (
    <div className="chart">
      <svg
        viewBox={`0 0 700 ${height}`}
        role="img"
        aria-label={labels.join(" versus ")}
        preserveAspectRatio="none"
      >
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <line
              x1="32"
              x2="696"
              y1={(i * (height - 24)) / 3 + 6}
              y2={(i * (height - 24)) / 3 + 6}
              stroke="#e5efeb"
              strokeDasharray="3 6"
            />
            <text
              x="0"
              y={(i * (height - 24)) / 3 + 12}
              fill="#738980"
              fontSize="10"
            >
              {fmt(max * (1 - i / 3), max <= 1 ? 2 : 0)}
            </text>
          </g>
        ))}
        {series.map((s, i) => (
          <polyline
            key={i}
            fill="none"
            stroke={colors[i % 3]}
            strokeWidth="2.5"
            strokeDasharray={i === 1 ? "7 4" : i === 2 ? "2 4" : undefined}
            strokeLinecap="round"
            strokeLinejoin="round"
            points={s
              .map(
                (v, j) =>
                  `${32 + (j * 660) / Math.max(1, s.length - 1)},${height - 18 - (v / max) * (height - 24)}`,
              )
              .join(" ")}
          />
        ))}
      </svg>
      <div className="legend">
        {labels.map((l, i) => (
          <span key={l}>
            <i style={{ background: colors[i % 3] }} />
            {l}
          </span>
        ))}
        <span className="ml-auto">Most recent 60 updates</span>
      </div>
    </div>
  );
}
function Panel({
  title,
  subtitle,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <section className={"panel " + (wide ? "wide" : "")}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        <span className="dots">···</span>
      </div>
      {children}
    </section>
  );
}
function App() {
  const dialogRef = useRef<HTMLElement>(null);
  const [page, setPage] = useState("Overview"),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null),
    [history, setHistory] = useState<Snapshot[]>([]),
    [connected, setConnected] = useState(false),
    [error, setError] = useState(""),
    [note, setNote] = useState(""),
    [selected, setSelected] = useState<string | null>(null),
    [detail, setDetail] = useState<{ current: Row; history: Row[] } | null>(
      null,
    ),
    [config, setConfig] = useState<Config | null>(null),
    [sim, setSim] = useState<Sim[]>([]),
    [frames, setFrames] = useState(8),
    [busy, setBusy] = useState(false),
    [experiments, setExperiments] = useState<Experiment[]>([]);
  function navigate(next: string) {
    if (next === page) return;
    setPage(next);
    setSelected(null);
    setDetail(null);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  useEffect(() => {
    let socket: WebSocket;
    let timer: ReturnType<typeof setTimeout>;
    let alive = true;
    const connect = () => {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`,
      );
      socket.onopen = () => { setConnected(true); setConfig(null); };
      socket.onmessage = (e) => {
        const s = JSON.parse(e.data) as Snapshot;
        setSnapshot(s);
        setHistory((h) => [...h.slice(-59), s]);
        setConfig((c) => s.mode === "live" ? s.settings : c ?? s.settings);
      };
      socket.onclose = () => {
        setConnected(false);
        if (alive) timer = setTimeout(connect, 1500);
      };
      socket.onerror = () => socket.close();
    };
    connect();
    return () => {
      alive = false;
      clearTimeout(timer);
      socket?.close();
    };
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    setDetail(null);
    async function refresh() {
      if (!selected) return;
      try {
        const result = await api("/processes/" + encodeURIComponent(selected));
        if (active) { setDetail(result); timer = setTimeout(refresh, 1500); }
      } catch (e) { if (active) setError(String(e)); }
    }
    refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [selected]);
  const detailOpen = Boolean(selected && detail);
  useEffect(() => {
    if (!detailOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    dialog?.querySelector<HTMLButtonElement>("button")?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") { setSelected(null); setDetail(null); }
      if (event.key === "Tab") {
        const controls = dialog?.querySelectorAll<HTMLElement>("button:not(:disabled), a[href], input:not(:disabled), [tabindex='0']");
        if (!controls?.length) return;
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => { document.removeEventListener("keydown", keyboard); previous?.focus(); };
  }, [detailOpen]);
  useEffect(() => {
    if (page === "Experiments" && connected)
      api("/experiments")
        .then((x) => {
          setExperiments(x.linux);
          if (x.simulator[0]) setSim(x.simulator[0].results);
        })
        .catch((e) => setError(e.message));
  }, [page, connected]);
  async function action(fn: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    try {
      await fn();
      setNote(message);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  const rows = snapshot?.processes ?? [],
    sum = (key: keyof Row) => rows.reduce((a, r) => a + Number(r[key] ?? 0), 0),
    series = (key: keyof Row) =>
      history.map((s) =>
        s.processes.reduce((a, r) => a + Number(r[key] ?? 0), 0),
      ),
    live = snapshot?.mode === "live";
  const processTable = (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {[
              "PROCESS / PID",
              "CPU",
              "MEMORY",
              "EWMA",
              "FAULTS / S",
              "SCORE",
              "WEIGHT",
              "STATE",
            ].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.identity}
              onClick={() => setSelected(r.identity)}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && setSelected(r.identity)}
            >
              <td>
                <div className="process-name">
                  <span className={"process-icon color" + i}>
                    <Cpu size={15} />
                  </span>
                  <span>
                    {r.name}
                    <small>
                      {r.pid} · {r.group}
                    </small>
                  </span>
                </div>
              </td>
              <td>{fmt(r.cpu)}%</td>
              <td>{fmt(r.memory_mb, 0)} MB</td>
              <td>{fmt(r.ewma)} ms</td>
              <td>{fmt(r.faults, 0)}</td>
              <td>{fmt(r.score, 2)}</td>
              <td>{r.cpu_weight}</td>
              <td>
                <span className={"badge " + r.status.toLowerCase()}>
                  {r.training ? "TRAINING" : r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && (
        <div className="empty">Waiting for managed workload telemetry…</div>
      )}
    </div>
  );
  return (
    <div className="shell">
      <aside>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("Overview");
          }}
        >
          <span className="brandmark">
            <Layers size={24} />
          </span>
          <span>
            BARG<small>RESOURCE GOVERNANCE</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((p, i) => {
            const Icon = icons[i];
            return (
              <button
                key={p}
                className={page === p ? "active" : ""}
                onClick={() => navigate(p)}
                aria-current={page === p ? "page" : undefined}
              >
                <Icon size={18} />
                {p}
                {page === p && <span className="nav-dot" />}
              </button>
            );
          })}
        </nav>
        <div className="aside-bottom">
          <div className="node">
            <span className="online-dot" />
            <span>
              {live ? "Ubuntu · managed host" : "Local demonstration"}
              <small>
                {live ? "Read-only dashboard" : "Synthetic telemetry stream"}
              </small>
            </span>
          </div>
          <p>
            Behavior-aware by design.
            <br />
            Observable at every step.
          </p>
          <div className="version">
            BARG RESEARCH PROTOTYPE <span>v1.0</span>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <span>{page}</span>
          </div>
          <div className="header-status">
            <span className={"online-dot " + (!connected ? "offline" : "")} />
            {connected ? "Stream connected" : "Reconnecting"}
            <span className="divider" />
            <span>
              {snapshot
                ? new Date(snapshot.timestamp * 1000).toLocaleTimeString()
                : "—"}
            </span>
          </div>
        </header>
        <div className="content" key={page}>
          <div className="heading">
            <div>
              <div className="eyebrow">INTELLIGENT OS RESOURCE GOVERNANCE</div>
              <h1>{page === "Overview" ? "System overview" : page}</h1>
              <p>One behavioral pipeline. Coordinated resource decisions.</p>
            </div>
            <a
              className="button secondary"
              href="/api/export/telemetry?format=csv"
              download
            >
              <Download size={15} /> Export telemetry
            </a>
          </div>
          <div className={"mode-banner " + (live ? "live" : "")}>
            <Radio size={17} />
            <strong>{live ? "LIVE LINUX TELEMETRY" : "SIMULATION MODE"}</strong>
            <span>
              {live
                ? "Controls are managed by the local Linux agent."
                : "Deterministic demo data · no kernel tracing or host resource changes"}
            </span>
            <span className="ml-auto">
              {!snapshot ? "Waiting for backend" : snapshot.settings.monitoring_only
                ? "Monitoring only"
                : "Adaptive control enabled"}
            </span>
          </div>
          {!connected && (
            <div className="error" role="status">
              Backend connection required. Start the Python server and open
              {" "}<a href="http://127.0.0.1:8000/">the local dashboard</a>.
              GitHub Pages can host the interface, but cannot run Python or the Linux agent.
              {" "}<a href="https://github.com/mehulkumar2024-art/BARG/blob/main/docs/STEP_BY_STEP.md" target="_blank" rel="noreferrer">Step-by-step setup guide</a>.
              {snapshot && " Displayed values are from the last received update."}
            </div>
          )}
          {(error || snapshot?.error || snapshot?.collector_error) && (
            <div className="error" role="alert">
              {error || snapshot?.error || snapshot?.collector_error}
            </div>
          )}
          {snapshot?.stale && (
            <div className="error">
              Telemetry is stale. Check the backend or Linux agent before interpreting
              these values.
            </div>
          )}
          {note && (
            <button className="notice" onClick={() => setNote("")}>
              {note} · Dismiss
            </button>
          )}
          {(page === "Overview" ||
            page === "CPU analytics" ||
            page === "Memory analytics") && (
            <div className="stats">
              {[
                {
                  label: "MANAGED CPU",
                  value: fmt(sum("cpu")),
                  unit: "% of one core",
                  icon: Cpu,
                  sub: `${rows.length} active workloads`,
                },
                {
                  label: "RESIDENT MEMORY",
                  value: fmt(sum("memory_mb"), 0),
                  unit: "MB",
                  icon: Database,
                  sub: "Combined process RSS",
                },
                {
                  label: "PAGE FAULTS",
                  value: fmt(sum("faults"), 0),
                  unit: "/ sec",
                  icon: Activity,
                  sub: "Minor + major faults",
                },
                {
                  label: "BEHAVIORAL ALERTS",
                  value: String(
                    snapshot?.alerts.filter((a) => a.status === "ANOMALOUS")
                      .length ?? 0,
                  ),
                  unit: "confirmed",
                  icon: ShieldCheck,
                  sub: `${rows.filter((r) => r.training).length} profiles training`,
                },
              ].map((m) => (
                <div className="stat" key={m.label}>
                  <div className="stat-label">
                    {m.label}
                    <m.icon size={18} />
                  </div>
                  <div className="stat-value">
                    {m.value}
                    <span>{m.unit}</span>
                  </div>
                  <small>
                    <span className="tiny-dot" />
                    {m.sub}
                  </small>
                </div>
              ))}
            </div>
          )}
          <div className="grid">
            {(page === "Overview" || page === "CPU analytics") && (
              <>
                <Panel
                  title="CPU activity"
                  subtitle="Managed workloads · percent of one CPU"
                >
                  <Chart
                    series={rows.map((r) =>
                      history.map(
                        (s) =>
                          s.processes.find((p) => p.identity === r.identity)
                            ?.cpu ?? 0,
                      ),
                    )}
                    labels={rows.map((r) => r.name)}
                  />
                </Panel>
                <Panel
                  title="Behavioral pulse"
                  subtitle="Composite anomaly score · bounded 0–1"
                >
                  <Chart
                    series={rows.map((r) =>
                      history.map(
                        (s) =>
                          s.processes.find((p) => p.identity === r.identity)
                            ?.score ?? 0,
                      ),
                    )}
                    labels={rows.map((r) => r.name)}
                  />
                </Panel>
              </>
            )}
            {(page === "Overview" || page === "Processes") && (
              <Panel
                title="Managed processes"
                subtitle="Select a workload to inspect its behavioral profile"
                wide
              >
                {processTable}
              </Panel>
            )}
            {page === "Overview" && (
              <>
                <Panel
                  title="Closed-loop health"
                  subtitle="From observation to a measured response"
                >
                  <div className="health">
                    <div>
                      <span>Collector</span>
                      <strong>{snapshot?.collector ?? "Waiting"}</strong>
                    </div>
                    <div>
                      <span>Jain’s CPU fairness</span>
                      <strong>{fmt(snapshot?.fairness, 3)}</strong>
                    </div>
                    <div>
                      <span>Syscalls / second</span>
                      <strong>
                        {fmt(
                          rows.reduce((total, row) => total + row.syscall_count / (row.interval_s || 1), 0),
                          0,
                        )}
                      </strong>
                    </div>
                    <div>
                      <span>Kernel ring-buffer drops</span>
                      <strong>
                        {fmt(Math.max(0, ...rows.map((r) => r.drops)), 0)}
                      </strong>
                    </div>
                    <div>
                      <span>Sequence truncations this window</span>
                      <strong>{fmt(sum("sequence_truncated"), 0)}</strong>
                    </div>
                  </div>
                </Panel>
                <Panel
                  title="Recent decisions"
                  subtitle="Auditable control actions and observations"
                >
                  <div className="event-list">
                    {snapshot?.decisions
                      .slice(-3)
                      .reverse()
                      .map((d, i) => (
                        <div className="event" key={i}>
                          <span className="event-icon">
                            <GitBranch size={16} />
                          </span>
                          <div>
                            <strong>{d.reason}</strong>
                            <small>
                              {d.identity} ·{" "}
                              {new Date(
                                d.timestamp * 1000,
                              ).toLocaleTimeString()}
                            </small>
                          </div>
                          <span className="badge">
                            {Object.keys(d.changes).length
                              ? "APPLIED"
                              : "OBSERVED"}
                          </span>
                        </div>
                      ))}
                  </div>
                </Panel>
              </>
            )}
            {page === "CPU analytics" && (
              <>
                <Panel
                  title="Burst prediction"
                  subtitle="First managed process · milliseconds"
                >
                  <Chart
                    series={[
                      history.map((s) => s.processes[0]?.burst_ms ?? 0),
                      history.map((s) => s.processes[0]?.prediction ?? 0),
                    ]}
                    labels={["Observed burst", "Previous EWMA prediction"]}
                  />
                </Panel>
                <Panel
                  title="Scheduler context"
                  subtitle="Scheduling measurements and proportional shares"
                >
                  <Chart
                    series={[series("switches")]}
                    labels={["Context switches per window"]}
                  />
                  <div className="health">
                    <div>
                      <span>Jain’s fairness (CPU usage)</span>
                      <strong>{fmt(snapshot?.fairness, 3)}</strong>
                    </div>
                    <div>
                      <span>CPU weights</span>
                      <strong>
                        {rows.map((r) => r.cpu_weight).join(" / ")}
                      </strong>
                    </div>
                  </div>
                </Panel>
              </>
            )}
            {page === "Memory analytics" && (
              <>
                <Panel title="Resident memory" subtitle="Process RSS · MB">
                  <Chart
                    series={[series("memory_mb")]}
                    labels={["Resident memory"]}
                  />
                </Panel>
                <Panel
                  title="Fault frequency"
                  subtitle="Faults are not a cache hit-rate measurement"
                >
                  <Chart
                    series={[series("faults")]}
                    labels={["Page faults / second"]}
                  />
                </Panel>
                <Panel
                  title="Memory pressure"
                  subtitle="Per-cgroup PSI some avg10 · percent"
                >
                  <Chart
                    series={rows.map((r) =>
                      history.map(
                        (s) =>
                          s.processes.find((p) => p.identity === r.identity)
                            ?.pressure ?? 0,
                      ),
                    )}
                    labels={rows.map((r) => r.name)}
                  />
                </Panel>
                <Panel
                  title="Memory policy"
                  subtitle="Bounded protection, with restoration"
                >
                  <p className="body-copy">
                    The policy adjusts memory.low in steps of at most 8 MiB,
                    with a 64 MiB budget per workload. A confirmed anomaly does
                    not receive additional protection. Proactive reclaim and
                    memory.max tuning are intentionally disabled.
                  </p>
                  <button
                    className="button secondary"
                    onClick={() => navigate("Experiments")}
                  >
                    Compare replacement algorithms <ArrowUpRight size={16} />
                  </button>
                </Panel>
              </>
            )}
            {page === "Security" && (
              <>
                <Panel
                  title="Anomaly scores"
                  subtitle="Three consecutive high windows confirm an anomaly"
                >
                  <Chart
                    series={rows.map((r) =>
                      history.map(
                        (s) =>
                          s.processes.find((p) => p.identity === r.identity)
                            ?.score ?? 0,
                      ),
                    )}
                    labels={rows.map((r) => r.name)}
                  />
                  {!live && (
                    <button
                      disabled={!connected || busy || rows.some((r) => r.training)}
                      className="button"
                      onClick={() =>
                        action(
                          () => api("/demo/anomaly", "POST"),
                          "Injected a 20-window synthetic behavior shift.",
                        )
                      }
                    >
                      <Play size={15} /> Inject safe demo anomaly
                    </button>
                  )}
                </Panel>
                <Panel
                  title="Syscall distribution"
                  subtitle="Sliding unigram frequencies · first process"
                >
                  {Object.entries(rows[0]?.distribution ?? {}).map(
                    ([id, p]) => (
                      <div className="bar-row" key={id}>
                        <span>Syscall {id}</span>
                        <div>
                          <i style={{ width: `${p * 100}%` }} />
                        </div>
                        <strong>{fmt(p * 100)}%</strong>
                      </div>
                    ),
                  )}
                </Panel>
                <Panel
                  title="Detection timeline"
                  subtitle="State changes, response decisions, and recovery"
                  wide
                >
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>TIME</th>
                          <th>IDENTITY</th>
                          <th>STATE</th>
                          <th>SCORE</th>
                          <th>RESPONSE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {snapshot?.alerts
                          .slice()
                          .reverse()
                          .map((a, i) => (
                            <tr key={i}>
                              <td>
                                {new Date(
                                  a.timestamp * 1000,
                                ).toLocaleTimeString()}
                              </td>
                              <td>{a.identity}</td>
                              <td>
                                <span
                                  className={"badge " + a.status.toLowerCase()}
                                >
                                  {a.status}
                                </span>
                              </td>
                              <td>{fmt(a.score, 3)}</td>
                              <td>{a.response}</td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                    {!snapshot?.alerts.length && (
                      <div className="empty">
                        No state transitions recorded. Baselines train before
                        assessment.
                      </div>
                    )}
                  </div>
                </Panel>
              </>
            )}
            {page === "Feedback engine" && (
              <>
                <Panel
                  title="A shared signal. A coordinated response."
                  subtitle="Every module consumes the same workload identity and behavioral profile"
                  wide
                >
                  <div className="pipeline">
                    {[
                      "Collect",
                      "Profile",
                      "Detect",
                      "Decide",
                      "Validate",
                      "Actuate",
                      "Measure",
                    ].map((p, i) => (
                      <React.Fragment key={p}>
                        <div>
                          <span>0{i + 1}</span>
                          <strong>{p}</strong>
                          <small>
                            {
                              [
                                "eBPF / demo",
                                "EWMA + n-grams",
                                "Normalized score",
                                "Joint CPU + memory",
                                "Scope + bounds",
                                "cgroup readback",
                                "Next-window delta",
                              ][i]
                            }
                          </small>
                        </div>
                        {i < 6 && <ChevronRight size={18} />}
                      </React.Fragment>
                    ))}
                  </div>
                </Panel>
                <Panel
                  title="Decision audit"
                  subtitle="Before / after values and measured outcomes"
                  wide
                >
                  <div className="audit">
                    {snapshot?.decisions
                      .slice(-12)
                      .reverse()
                      .map((d, i) => (
                        <div key={i}>
                          <div>
                            <span className="mono">
                              {new Date(
                                d.timestamp * 1000,
                              ).toLocaleTimeString()}
                            </span>
                            <strong>{d.identity}</strong>
                            <span>{d.reason}</span>
                          </div>
                          <pre>
                            {JSON.stringify(
                              {
                                changes: d.changes,
                                after: d.after,
                                outcome: d.outcome,
                              },
                              null,
                              2,
                            )}
                          </pre>
                        </div>
                      ))}
                  </div>
                </Panel>
              </>
            )}
            {page === "Experiments" && (
              <>
                <Panel
                  title="Page-replacement laboratory"
                  subtitle="Seed 42 · 5,000 synthetic references · results computed by Python and saved locally"
                  wide
                >
                  <div className="experiment-toolbar">
                    <label>
                      Frames{" "}
                      <input
                        type="number"
                        min="1"
                        max="128"
                        value={frames}
                        onChange={(e) => setFrames(Number(e.target.value))}
                      />
                    </label>
                    <button
                      className="button"
                      disabled={!connected || busy}
                      onClick={() =>
                        action(
                          async () =>
                            setSim(
                              await api("/experiments/simulator", "POST", {
                                frames,
                                length: 5000,
                                seed: 42,
                              }),
                            ),
                          "Simulation completed and stored.",
                        )
                      }
                    >
                      <Play size={15} /> Run comparison
                    </button>
                    <a
                      className="button secondary"
                      href="/api/export/simulator?format=csv"
                      download
                    >
                      <Download size={15} /> CSV
                    </a>
                  </div>
                  <div className="sim-grid">
                    {sim.map((s) => (
                      <div key={s.policy}>
                        <span>{s.policy}</span>
                        <strong>
                          {fmt(s.hit_ratio * 100)}
                          <small>% hit ratio</small>
                        </strong>
                        <div className="sim-bar">
                          <i style={{ width: `${s.hit_ratio * 100}%` }} />
                        </div>
                        <p>
                          {s.faults} faults · {fmt(s.execution_ms, 2)} ms
                        </p>
                      </div>
                    ))}
                  </div>
                </Panel>
                <Panel
                  title="Linux experiment matrix"
                  subtitle="Real results appear only after the Ubuntu evaluation suite runs"
                  wide
                >
                  <table>
                    <thead>
                      <tr>
                        <th>CONFIGURATION</th>
                        <th>TELEMETRY</th>
                        <th>CPU</th>
                        <th>MEMORY</th>
                        <th>RESULT</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        "Vanilla Linux",
                        "Monitoring only",
                        "CPU tuning only",
                        "Memory governance only",
                        "Full BARG",
                      ].map((m, i) => (
                        <tr key={m}>
                          <td>{m}</td>
                          <td>{i ? "eBPF" : "Off"}</td>
                          <td>{i === 2 || i === 4 ? "Adaptive" : "Default"}</td>
                          <td>{i >= 3 ? "Adaptive" : "Default"}</td>
                          <td>
                            <span className="badge">
                              {experiments.some((r) => r.mode === ["vanilla", "monitor", "cpu", "memory", "full"][i])
                                ? "See JSON export"
                                : "NOT MEASURED"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="body-copy">
                    Run <code>sudo bash scripts/run_benchmarks.sh</code> in the
                    Ubuntu VM. Results include configuration, repeated trials,
                    workload throughput, decision logs, and unavailable metric
                    reasons.
                  </p>
                  <a
                    href="/api/export/experiment"
                    className="button secondary"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Export recorded experiments <ArrowUpRight size={15} />
                  </a>
                </Panel>
              </>
            )}
            {page === "Settings" && config && (
              <Panel
                title="Policy & safety"
                subtitle={
                  live
                    ? "Live settings are read-only. Restart the local agent with the desired mode."
                    : "Changes affect only the simulated controller."
                }
                wide
              >
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    action(
                      async () =>
                        setConfig(await api("/settings", "PUT", config)),
                      "Settings saved.",
                    );
                  }}
                >
                  <div className="settings-grid">
                    {(
                      [
                        "monitoring_only",
                        "cpu_enabled",
                        "memory_enabled",
                        "anomaly_response",
                      ] as const
                    ).map((k) => (
                      <label className="toggle-row" key={k}>
                        <span>
                          {k.replaceAll("_", " ")}
                          <small>
                            {k === "monitoring_only"
                              ? "Observe without applying resource changes"
                              : "Explicitly enable this policy component"}
                          </small>
                        </span>
                        <input
                          type="checkbox"
                          checked={config[k]}
                          disabled={live}
                          onChange={(e) =>
                            setConfig({ ...config, [k]: e.target.checked })
                          }
                        />
                      </label>
                    ))}
                    {(
                      [
                        { key: "alpha", min: 0.01, max: 1, step: 0.01 },
                        { key: "threshold", min: 0.2, max: 0.95, step: 0.01 },
                        { key: "interval", min: 0.5, max: 10, step: 0.5 },
                        { key: "training_windows", min: 5, max: 120, step: 1 },
                        { key: "cooldown", min: 2, max: 120, step: 1 },
                      ] as const
                    ).map((f) => (
                      <label className="number-row" key={f.key}>
                        <span>{f.key.replaceAll("_", " ")}</span>
                        <input
                          type="number"
                          disabled={live}
                          {...f}
                          value={config[f.key]}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              [f.key]: Number(e.target.value),
                            })
                          }
                        />
                      </label>
                    ))}
                  </div>
                  <div className="actions">
                    <button className="button" disabled={!connected || live || busy}>
                      Save configuration
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={!connected || live || busy}
                      onClick={() =>
                        action(async () => {
                          await api("/restore", "POST");
                          setConfig(await api("/settings"));
                        }, "Original allocations restored. Monitoring-only mode enabled.")
                      }
                    >
                      <RotateCcw size={15} /> Restore original allocations
                    </button>
                  </div>
                </form>
              </Panel>
            )}
            {page === "Experiments" && experiments.length > 0 && (
              <Panel
                title="Recorded Linux trials"
                subtitle="Real measurements · compare throughput only within a workload kind"
                wide
              >
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        {[
                          "WORKLOAD",
                          "MODE / TRIAL",
                          "OPS / S",
                          "AGENT CPU¹",
                          "PEAK RSS",
                          "JAIN INDEX",
                          "CHANGES",
                          "PRECISION / RECALL",
                        ].map((h) => (
                          <th key={h}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {experiments.map((r, i) => (
                        <tr key={i}>
                          <td>{r.kind}</td>
                          <td>
                            {r.mode} / {r.repeat + 1}
                          </td>
                          <td>{fmt(r.throughput_ops_s)}</td>
                          <td>{fmt(r.agent_cpu_core_percent)}%</td>
                          <td>{fmt(r.agent_peak_rss_mb)} MB</td>
                          <td>{fmt(r.jain_cpu_fairness, 3)}</td>
                          <td>{r.resource_changes}</td>
                          <td>
                            {r.detection?.precision == null
                              ? "—"
                              : fmt(r.detection.precision, 3)}{" "}
                            /{" "}
                            {r.detection?.recall == null
                              ? "—"
                              : fmt(r.detection.recall, 3)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="body-copy">
                  ¹ Agent CPU is percent of one core and excludes kernel
                  tracing, server, and browser costs.
                </p>
                {["cpu", "memory", "io", "anomaly"].map((kind) => {
                  const subset = experiments.filter((r) => r.kind === kind);
                  const peak = Math.max(
                    1,
                    ...subset.map((r) => r.throughput_ops_s),
                  );
                  return (
                    <div key={kind}>
                      <h2>{kind} · operations / second</h2>
                      {subset.map((r, i) => (
                        <div className="bar-row" key={i}>
                          <span>
                            {r.mode} #{r.repeat + 1}
                          </span>
                          <div>
                            <i
                              style={{
                                width: `${(r.throughput_ops_s / peak) * 100}%`,
                              }}
                            />
                          </div>
                          <strong>{fmt(r.throughput_ops_s, 0)}</strong>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </Panel>
            )}
          </div>
          <footer>
            <span>BARG · Behavior-Aware Resource Governance</span>
            <span>
              {live ? "Linux measurements" : "All telemetry shown is synthetic"}{" "}
              · Bounded telemetry with explicit loss counters
            </span>
          </footer>
        </div>
      </main>
      {selected && detail && (
        <div
          className="modal-backdrop"
          onClick={() => {
            setSelected(null);
            setDetail(null);
          }}
        >
          <section
            ref={dialogRef}
            className="modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Process details"
          >
            <button
              className="close"
              aria-label="Close process details"
              onClick={() => {
                setSelected(null);
                setDetail(null);
              }}
            >
              ×
            </button>
            <div className="eyebrow">PROCESS PROFILE</div>
            <h2>{detail.current.name}</h2>
            <p className="mono">{detail.current.identity}</p>
            <Chart
              series={[
                detail.history.map((r) => r.burst_ms),
                detail.history.map((r) => r.prediction ?? 0),
              ]}
              labels={["Observed burst ms", "EWMA prediction ms"]}
            />
            <pre>{JSON.stringify(detail.current, null, 2)}</pre>
            {!live && (
              <button
                className="button secondary"
                onClick={() =>
                  action(
                    () =>
                      api(
                        "/processes/" +
                          encodeURIComponent(selected) +
                          "/retrain",
                        "POST",
                      ),
                    "Baseline reset. New training period started.",
                  )
                }
              >
                Retrain baseline
              </button>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
