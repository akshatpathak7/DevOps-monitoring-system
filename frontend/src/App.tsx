import {
  createContext,
  FormEvent,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Bell,
  ChevronRight,
  Clock3,
  Database,
  FileText,
  FlaskConical,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  RefreshCw,
  Server,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  api,
  date,
  DemoStatus,
  Incident,
  label,
  Log,
  MetricName,
  number,
  Page,
  Point,
  post,
  query,
  Service,
  Session,
  Summary,
  usePoll,
} from "./api";

type AppContext = {
  session: Session;
  service: string;
  summary?: Summary;
  summaryError: string;
  login: () => void;
};
const metricUnits: Record<string, string> = {
  error_rate: "%",
  latency: "s",
  uptime: "s",
  cpu: "% of one core",
  memory: "MiB",
  requests_window: "requests / 60s",
};
const Context = createContext<AppContext>(null!);
const useApp = () => useContext(Context);
const titles: Record<string, string> = {
  "/": "Overview",
  "/metrics": "Metrics",
  "/logs": "Logs",
  "/incidents": "Incidents",
};

export default function App() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  const summary = usePoll<Summary>("/metrics/summary");
  const auth = usePoll<Session>("/auth/me", 30000);
  const [service, setService] = useState("");
  const [loginOpen, setLoginOpen] = useState(false);
  const [authError, setAuthError] = useState("");
  const session = auth.data || { authenticated: false };
  const selected =
    service || summary.data?.services[0]?.service_name || "demo-service";
  async function logout() {
    try {
      await post("/auth/logout", {}, session);
      auth.refresh();
      setAuthError("");
    } catch (e) {
      setAuthError((e as Error).message);
    }
  }
  return (
    <Context.Provider
      value={{
        session,
        service: selected,
        summary: summary.data,
        summaryError: summary.error,
        login: () => setLoginOpen(true),
      }}
    >
      <div className="app-shell">
        <aside className="sidebar">
          <Link to="/" className="brand">
            <span className="brand-symbol">
              <Activity size={23} />
            </span>
            <span>
              DevOps<span className="brand-sub">MONITORING SYSTEM</span>
            </span>
          </Link>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {[
              ["/", LayoutDashboard, "Overview"],
              ["/metrics", BarChart3, "Metrics"],
              ["/logs", FileText, "Logs"],
              ["/incidents", Bell, "Incidents"],
            ].map(([path, Icon, title]) => {
              const NavIcon = Icon as typeof Activity;
              return (
                <NavLink
                  aria-label={String(title)}
                  key={String(path)}
                  to={String(path)}
                  end={path === "/"}
                >
                  <NavIcon size={18} />
                  <span>{String(title)}</span>
                  {path === "/incidents" && (
                    <span className="nav-count">
                      {summary.data?.services.reduce(
                        (n, s) => n + s.open_incidents,
                        0,
                      ) ?? "—"}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
          <div className="sidebar-bottom">
            <div className="environment">
              <span className="dot" /> DEMO ENVIRONMENT
            </div>
            <p>
              Observe. Understand.
              <br />
              Troubleshoot with context.
            </p>
            <div className="stack-note">
              <Database size={14} /> Prometheus + PostgreSQL
            </div>
          </div>
        </aside>
        <div className="workspace">
          <header className="topbar">
            <div className="breadcrumb">
              Workspace <ChevronRight size={14} />{" "}
              <strong>{titles[location.pathname] || "Incident detail"}</strong>
            </div>
            <div className="top-actions">
              <span className="read-only">
                {session.authenticated ? "Admin access" : "Public view"}
              </span>
              {session.authenticated ? (
                <button className="quiet" onClick={logout}>
                  <LogOut size={15} /> Sign out
                </button>
              ) : (
                <button className="quiet" onClick={() => setLoginOpen(true)}>
                  <LockKeyhole size={15} /> Admin login
                </button>
              )}
            </div>
          </header>
          <main>
            {(auth.error || authError) && (
              <Notice error={auth.error || authError} />
            )}
            <div className="page-heading">
              <div>
                <div className="eyebrow">APPLICATION OBSERVABILITY</div>
                <h1>{titles[location.pathname] || "Incident detail"}</h1>
                <p className="subtitle">
                  Your application’s health, with the context to act.
                </p>
              </div>
              <div className="service-picker">
                <Server size={16} />
                <select
                  aria-label="Monitored service"
                  value={selected}
                  onChange={(e) => setService(e.target.value)}
                >
                  {(
                    summary.data?.services || [{ service_name: "demo-service" }]
                  ).map((s) => (
                    <option key={s.service_name}>{s.service_name}</option>
                  ))}
                </select>
              </div>
            </div>
            {summary.error && (
              <Notice
                error={`Monitoring summary unavailable: ${summary.error}. Last successful data may be stale.`}
              />
            )}
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/metrics" element={<Metrics />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/incidents" element={<Incidents />} />
              <Route path="/incidents/:id" element={<IncidentDetail />} />
              <Route
                path="*"
                element={
                  <Empty
                    title="Page not found"
                    text="Choose a page in the navigation to continue."
                  />
                }
              />
            </Routes>
            <footer>
              <span>
                <span className="dot" />{" "}
                {summary.error
                  ? "Connection interrupted"
                  : "Auto-refresh every 5 seconds"}
              </span>
              <span>
                Last updated {summary.updated?.toLocaleTimeString() || "—"} ·
                Times shown locally
              </span>
            </footer>
          </main>
        </div>
      </div>
      {loginOpen && (
        <Login
          onClose={() => setLoginOpen(false)}
          onSuccess={() => {
            auth.refresh();
            setLoginOpen(false);
          }}
        />
      )}
    </Context.Provider>
  );
}

function Notice({ error }: { error: string }) {
  return error ? (
    <div role="alert" className="notice">
      {error}
    </div>
  ) : null;
}
function Empty({ title, text }: { title: string; text?: string }) {
  return (
    <div className="empty">
      <Activity size={26} />
      <strong>{title}</strong>
      {text && <p>{text}</p>}
    </div>
  );
}
function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value}`}>
      <span className="dot" />
      {label(value)}
    </span>
  );
}
function Panel({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function MetricCard({
  title,
  value,
  unit,
  note,
  icon: Icon,
}: {
  title: string;
  value: string;
  unit?: string;
  note: string;
  icon: typeof Activity;
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">
        {title}
        <Icon size={17} />
      </div>
      <div className="metric-value">
        {value}
        <span>{unit}</span>
      </div>
      <div className="metric-note">{note}</div>
    </div>
  );
}
function currentService(
  summary: Summary | undefined,
  service: string,
): Service | undefined {
  return summary?.services.find((s) => s.service_name === service);
}

function Overview() {
  const { summary, service, summaryError } = useApp();
  const current = currentService(summary, service);
  const incidents = usePoll<Page<Incident>>(
    "/incidents" + query({ service_name: service, status: "open", limit: 5 }),
  );
  const m = summaryError ? undefined : current?.metrics;
  return (
    <>
      <div className="status-strip">
        <div className="status-icon">
          <Server size={20} />
        </div>
        <div>
          <strong>{service}</strong>
          <p>
            {summaryError || current?.status === "unknown"
              ? "Monitoring data is unavailable. Service health is unknown."
              : current?.status === "unavailable"
                ? "Prometheus cannot reach this service’s metrics."
                : current?.status === "degraded"
                  ? "Service is reachable; open incidents require attention."
                  : current
                    ? "Receiving application telemetry"
                    : "Waiting for the first metric samples…"}
          </p>
        </div>
        <Badge
          value={summaryError ? "unknown" : current?.status || "unknown"}
        />
      </div>
      <div className="metric-grid">
        <MetricCard
          title="Total requests"
          value={number(m?.request_count, 0)}
          note="Since the application process started"
          icon={ArrowUpRight}
        />
        <MetricCard
          title="HTTP error rate"
          value={number(m?.error_rate)}
          unit="%"
          note="5xx responses · rolling 1 minute"
          icon={Activity}
        />
        <MetricCard
          title="Response latency"
          value={number(m?.latency == null ? null : m.latency * 1000, 0)}
          unit="ms"
          note="95th percentile · rolling 1 minute"
          icon={Clock3}
        />
        <MetricCard
          title="Open incidents"
          value={summaryError ? "—" : number(current?.open_incidents, 0)}
          note="Active conditions requiring attention"
          icon={Bell}
        />
      </div>
      <div className="chart-grid">
        <MetricChart metric="error_rate" title="HTTP error rate" unit="%" />
        <MetricChart metric="latency" title="Response latency · p95" unit="s" />
      </div>
      <Panel
        title="Open incidents"
        subtitle="Deterministic alerts with preserved evidence"
        action={
          <Link className="text-link" to="/incidents">
            View all <ChevronRight size={14} />
          </Link>
        }
      >
        <Notice error={incidents.error} />
        {incidents.loading ? (
          <Empty title="Loading incidents…" />
        ) : (
          <IncidentTable incidents={incidents.data?.items || []} />
        )}
      </Panel>
      <Simulation />
    </>
  );
}

function MetricChart({
  metric,
  title,
  unit = "",
  minutes = 15,
}: {
  metric: MetricName;
  title: string;
  unit?: string;
  minutes?: number;
}) {
  const { service } = useApp();
  const result = usePoll<{ points: Point[] }>(
    "/metrics/history" + query({ service_name: service, metric, minutes }),
  );
  const points = result.data?.points || [];
  const hasValues = points.some((p) => p.value != null);
  return (
    <Panel
      title={title}
      subtitle={`Last ${minutes < 60 ? minutes + " minutes" : minutes / 60 + " hours"}${unit ? " · " + unit : ""}`}
      action={
        <span className="chart-legend">
          <span /> {service}
        </span>
      }
    >
      <Notice error={result.error} />
      {result.loading ? (
        <Empty title="Loading metric history…" />
      ) : !hasValues ? (
        <Empty
          title="No samples available"
          text="Charts populate after Prometheus collects enough samples."
        />
      ) : (
        <div className="chart">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={points}
              margin={{ top: 10, right: 18, left: -14, bottom: 0 }}
            >
              <defs>
                <linearGradient
                  id={`fill-${metric}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor="#8067ed" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#8067ed" stopOpacity={0.01} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 5"
                vertical={false}
                stroke="#e9edf4"
              />
              <XAxis
                dataKey="timestamp"
                tickFormatter={(t) =>
                  new Date(t).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
                minTickGap={55}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#8892a4" }}
              />
              <YAxis
                tickFormatter={(v) => number(v)}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "#8892a4" }}
              />
              <Tooltip
                labelFormatter={(v) => date(String(v))}
                formatter={(v) => [`${number(Number(v), 3)} ${unit}`, title]}
                contentStyle={{
                  borderRadius: 10,
                  border: "1px solid #e8eaf0",
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#8067ed"
                strokeWidth={2}
                fill={`url(#fill-${metric})`}
                isAnimationActive={false}
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

function Metrics() {
  const [minutes, setMinutes] = useState(15);
  return (
    <>
      <div className="toolbar">
        <span>
          Application process metrics · resource usage is not host-wide
        </span>
        <select
          aria-label="Chart time range"
          value={minutes}
          onChange={(e) => setMinutes(Number(e.target.value))}
        >
          <option value={15}>Last 15 minutes</option>
          <option value={60}>Last hour</option>
          <option value={360}>Last 6 hours</option>
          <option value={1440}>Last 24 hours</option>
        </select>
      </div>
      <div className="chart-grid">
        {(
          [
            ["request_count", "Total requests", ""],
            ["error_rate", "HTTP error rate", "%"],
            ["latency", "Response latency · p95", "s"],
            ["uptime", "Application uptime", "s"],
            ["cpu", "Process CPU · one core", "%"],
            ["memory", "Process resident memory", "MiB"],
          ] as [MetricName, string, string][]
        ).map(([metric, title, unit]) => (
          <MetricChart
            key={metric}
            metric={metric}
            title={title}
            unit={unit}
            minutes={minutes}
          />
        ))}
      </div>
    </>
  );
}

function LogTable({ logs }: { logs: Log[] }) {
  if (!logs.length)
    return (
      <Empty
        title="No logs in this view"
        text="Try a different filter or wait for new application activity."
      />
    );
  return (
    <div className="table-scroll">
      <table className="log-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Service</th>
            <th>Level</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log, i) => (
            <tr key={log.id || `${log.timestamp}-${i}`}>
              <td className="nowrap">{date(log.timestamp)}</td>
              <td>
                <code>{log.service_name}</code>
              </td>
              <td>
                <Badge value={log.level.toLowerCase()} />
              </td>
              <td className="log-message">{log.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Pagination({
  total,
  offset,
  setOffset,
}: {
  total: number;
  offset: number;
  setOffset: (n: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${offset + 1}–${Math.min(offset + 50, total)} of ${total}`
          : "0 results"}
      </span>
      <div>
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous
        </button>
        <button
          disabled={offset + 50 >= total}
          onClick={() => setOffset(offset + 50)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
function Logs() {
  const { service } = useApp();
  return <LogView key={service} service={service} />;
}
function LogView({ service }: { service: string }) {
  const [level, setLevel] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [offset, setOffset] = useState(0);
  const result = usePoll<Page<Log>>(
    "/logs" +
      query({
        service_name: service,
        level,
        offset,
        since: since ? new Date(since).toISOString() : "",
        until: until ? new Date(until).toISOString() : "",
      }),
  );
  return (
    <Panel
      title="Application logs"
      subtitle="Synthetic demo events · 7-day retention"
      action={
        <button className="quiet" onClick={result.refresh}>
          <RefreshCw size={14} /> Refresh
        </button>
      }
    >
      <div className="filters">
        <label>
          Severity
          <select
            value={level}
            onChange={(e) => {
              setLevel(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All levels</option>
            {["DEBUG", "INFO", "WARNING", "ERROR"].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          From
          <input
            type="datetime-local"
            value={since}
            onChange={(e) => {
              setSince(e.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Until
          <input
            type="datetime-local"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              setOffset(0);
            }}
          />
        </label>
      </div>
      <Notice error={result.error} />
      {result.loading ? (
        <Empty title="Loading logs…" />
      ) : (
        <LogTable logs={result.data?.items || []} />
      )}
      <Pagination
        total={result.data?.total || 0}
        offset={offset}
        setOffset={setOffset}
      />
    </Panel>
  );
}

function IncidentTable({ incidents }: { incidents: Incident[] }) {
  if (!incidents.length)
    return (
      <Empty
        title="No incidents to show"
        text="Incidents appear when a monitored condition crosses its threshold."
      />
    );
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Incident</th>
            <th>Severity</th>
            <th>Detected</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {incidents.map((i) => (
            <tr key={i.id}>
              <td>
                <Link className="incident-link" to={`/incidents/${i.id}`}>
                  {i.title}
                </Link>
                <div className="cell-sub">
                  #{i.id} · {i.service_name} · {label(i.incident_type)}
                </div>
              </td>
              <td>
                <Badge value={i.severity} />
              </td>
              <td className="nowrap">{date(i.detected_at)}</td>
              <td>
                <Badge value={i.status} />
              </td>
              <td>
                <Link
                  aria-label={`Open incident ${i.id}`}
                  to={`/incidents/${i.id}`}
                >
                  <ChevronRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Incidents() {
  const { service } = useApp();
  return <IncidentList key={service} service={service} />;
}
function IncidentList({ service }: { service: string }) {
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const result = usePoll<Page<Incident>>(
    "/incidents" +
      query({ service_name: service, status, incident_type: kind, offset }),
  );
  return (
    <Panel
      title="Incident history"
      subtitle="One active incident per service and rule"
    >
      <div className="filters">
        <label>
          Status
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>
        <label>
          Type
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">All types</option>
            {[
              "http_errors",
              "latency",
              "unavailable",
              "error_logs",
              "cpu",
              "memory",
            ].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Notice error={result.error} />
      {result.loading ? (
        <Empty title="Loading incidents…" />
      ) : (
        <IncidentTable incidents={result.data?.items || []} />
      )}
      <Pagination
        total={result.data?.total || 0}
        offset={offset}
        setOffset={setOffset}
      />
    </Panel>
  );
}

function Simulation() {
  const { service, session, login } = useApp();
  const result = usePoll<DemoStatus>(
    "/demo/status" + query({ service_name: service }),
  );
  const [mode, setMode] = useState("http_errors");
  const [duration, setDuration] = useState(60);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function simulate() {
    setBusy(true);
    setError("");
    try {
      await post(
        "/demo/simulate-failure",
        { service_name: service, mode, duration_seconds: duration },
        session,
      );
      result.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="simulation">
      <div className="simulation-icon">
        <FlaskConical size={24} />
      </div>
      <div className="simulation-content">
        <h2>Put your monitoring to the test</h2>
        <p>
          Trigger a bounded failure, follow the evidence, and explore a
          troubleshooting explanation.
        </p>
        <Notice error={error || result.error} />
        {result.data?.mode && (
          <div className="active-simulation" role="status">
            Active: {label(result.data.mode)} · automatically ends{" "}
            {date(result.data.expires_at!)}
          </div>
        )}
        {session.authenticated ? (
          <div className="simulation-controls">
            <select
              aria-label="Failure mode"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="http_errors">HTTP errors</option>
              <option value="latency">Slow responses</option>
              <option value="error_logs">Error log burst</option>
              <option value="unavailable">Unavailable metrics</option>
            </select>
            <select
              aria-label="Failure duration"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            >
              <option value={30}>30 seconds</option>
              <option value={60}>60 seconds</option>
              <option value={120}>120 seconds</option>
            </select>
            <button
              className="primary"
              onClick={simulate}
              disabled={
                busy || !!result.data?.mode || !result.data || !!result.error
              }
            >
              <FlaskConical size={15} />
              {busy ? "Starting…" : "Simulate failure"}
            </button>
          </div>
        ) : (
          <button className="quiet purple" onClick={login}>
            <LockKeyhole size={14} /> Sign in as admin to simulate
          </button>
        )}
      </div>
      <span className="bounded-label">
        <ShieldCheck size={14} /> Auto-recovery
      </span>
    </section>
  );
}

function IncidentDetail() {
  const { id } = useParams();
  const { session, login } = useApp();
  const result = usePoll<Incident>(`/incidents/${id}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const incident = result.data;
  async function analyze() {
    setBusy(true);
    setError("");
    try {
      await post(`/incidents/${id}/analyze`, {}, session);
      result.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (!incident)
    return (
      <>
        <Notice error={result.error} />
        <Empty
          title={result.loading ? "Loading incident…" : "Incident unavailable"}
        />
      </>
    );
  return (
    <>
      <Link className="back-link" to="/incidents">
        ← All incidents
      </Link>
      <Notice error={result.error} />
      <section className="panel incident-summary">
        <div>
          <span className="eyebrow">
            INCIDENT #{incident.id} · {incident.service_name}
          </span>
          <h2>{incident.title}</h2>
          <p>{incident.description}</p>
          <div className="incident-meta">
            <span>
              <Clock3 size={14} /> Detected {date(incident.detected_at)}
            </span>
            <span>Last seen {date(incident.last_seen_at)}</span>
            {incident.resolved_at && (
              <span>Resolved {date(incident.resolved_at)}</span>
            )}
          </div>
        </div>
        <div className="badges">
          <Badge value={incident.severity} />
          <Badge value={incident.status} />
        </div>
      </section>
      <div className="detail-grid">
        <Panel
          title="Triggering evidence"
          subtitle={`Preserved at detection · ${incident.window_seconds}s rule window`}
        >
          <div className="evidence-primary">
            <span>{label(incident.metric_name)}</span>
            <strong>
              {number(incident.metric_value, 3)}{" "}
              {metricUnits[incident.metric_name] || ""}
            </strong>
            <small>
              Threshold: {incident.threshold}{" "}
              {metricUnits[incident.metric_name] || ""}{" "}
              {incident.incident_type === "unavailable"
                ? "(expected up = 1)"
                : ""}
            </small>
          </div>
          <dl className="evidence-list">
            {Object.entries(incident.metric_evidence).map(([k, v]) => (
              <div key={k}>
                <dt>{label(k)}</dt>
                <dd>
                  {number(v, 3)} {metricUnits[k] || ""}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>
        <Panel
          title="Troubleshooting assistant"
          subtitle="Evidence-informed guidance · no commands are executed"
          action={<Sparkles size={19} className="purple" />}
        >
          <div className="analysis-body">
            <Notice error={error} />
            {incident.analyzed_at ? (
              <>
                <div className="analysis-label">
                  <Sparkles size={14} />
                  {incident.analysis_source === "demo"
                    ? "Demo explanation"
                    : `AI explanation · ${incident.analysis_model}`}
                </div>
                <h3>Likely cause</h3>
                <p>{incident.likely_cause}</p>
                <h3>Explanation</h3>
                <p>{incident.ai_explanation}</p>
                <h3>Suggested troubleshooting steps</h3>
                <ol>
                  {incident.ai_recommendation?.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
                <div className="uncertainty">
                  <strong>Uncertainty</strong>
                  <p>{incident.uncertainty_note}</p>
                </div>
                <small className="muted">
                  Saved {date(incident.analyzed_at)}
                </small>
              </>
            ) : (
              <div className="analysis-empty">
                <div className="ai-orb">
                  <Sparkles size={28} />
                </div>
                <h3>Make sense of the signal</h3>
                <p>
                  Combine the triggering metrics and related logs into an
                  explanation and practical next steps.
                </p>
                {session.authenticated ? (
                  <button className="primary" disabled={busy} onClick={analyze}>
                    <Sparkles size={16} />
                    {busy ? "Analyzing incident…" : "Analyze incident"}
                  </button>
                ) : (
                  <button onClick={login}>
                    <LockKeyhole size={15} /> Admin login to analyze
                  </button>
                )}
                <small>
                  Without an API key, a clearly labeled demo explanation is
                  provided.
                </small>
              </div>
            )}
          </div>
        </Panel>
      </div>
      <Panel
        title="Related logs"
        subtitle="Up to 30 events from the two minutes before detection; retained with this incident"
      >
        <LogTable logs={incident.log_excerpt} />
      </Panel>
    </>
  );
}

function Login({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      onSuccess();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      className="modal-backdrop"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
      >
        <button
          className="modal-close quiet"
          aria-label="Close login"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        <span className="brand-symbol">
          <LockKeyhole size={22} />
        </span>
        <h2 id="login-title">Admin access</h2>
        <p>Sign in to simulate failures and request incident analysis.</p>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              autoFocus
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <Notice error={error} />
          <button className="primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </section>
    </div>
  );
}
