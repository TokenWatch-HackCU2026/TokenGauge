import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  fetchRecords, fetchSummary, fetchDashboardSummary,
  fetchTimeseries, fetchBreakdown, fetchQuota,
  fetchSdkToken, regenerateSdkToken,
  ApiCall, ApiCallSummary, TimeseriesPoint, BreakdownRow, UserOut,
} from "../api/client";

// ─── Theme ────────────────────────────────────────────────────────────────────
const C = {
  bg: "#0a0e1a",
  surface: "#111827",
  border: "#1e2d40",
  accent: "#6366f1",
  accentLight: "#818cf8",
  accentDim: "rgba(99,102,241,0.15)",
  green: "#10b981",
  red: "#ef4444",
  yellow: "#f59e0b",
  text: "#f1f5f9",
  muted: "#64748b",
  subtle: "#94a3b8",
} as const;

const PROVIDER_COLORS: Record<string, string> = {
  openai: "#10a37f",
  anthropic: "#d97706",
  google: "#4285f4",
  mistral: "#7c3aed",
};

const PIE_COLORS = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"];

// ─── Date range helpers ───────────────────────────────────────────────────────
function rangeToParams(range: string) {
  const now = new Date();
  const ms = range === "24h" ? 86_400_000 : range === "7d" ? 7 * 86_400_000 : 30 * 86_400_000;
  return { startDate: new Date(now.getTime() - ms).toISOString(), endDate: now.toISOString() };
}

// ─── Types ────────────────────────────────────────────────────────────────────
type Page = "overview" | "usage" | "settings";

const NAV_ITEMS: { id: Page; icon: string; label: string }[] = [
  { id: "overview", icon: "◈", label: "Overview" },
  { id: "usage", icon: "◉", label: "Usage" },
  { id: "settings", icon: "◎", label: "Settings" },
];

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function Dashboard({ onLogout, user }: { onLogout?: () => void; user?: UserOut | null }) {
  const [page, setPage] = useState<Page>("overview");
  const [range, setRange] = useState("7d");
  const params = rangeToParams(range);

  const { data: dashSummary } = useQuery({
    queryKey: ["dashboard-summary", range],
    queryFn: () => fetchDashboardSummary(params),
  });
  const { data: timeseries = [] } = useQuery({
    queryKey: ["timeseries", range],
    queryFn: () => fetchTimeseries({ ...params, groupBy: range === "24h" ? "hour" : "day" }),
  });
  const { data: breakdown = [] } = useQuery({
    queryKey: ["breakdown", range],
    queryFn: () => fetchBreakdown(params),
  });
  const { data: summary = [] } = useQuery({
    queryKey: ["summary"],
    queryFn: fetchSummary,
  });
  const { data: records = [], isLoading } = useQuery({
    queryKey: ["records"],
    queryFn: () => fetchRecords(100),
  });
  const { data: quota } = useQuery({
    queryKey: ["quota"],
    queryFn: fetchQuota,
  });

  return (
    <div style={{ display: "flex", height: "100vh", background: C.bg, color: C.text, fontFamily: "'Inter', system-ui, sans-serif", overflow: "hidden" }}>
      {/* ── Sidebar ── */}
      <aside style={{ width: 220, background: C.surface, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ padding: "1.5rem 1.25rem 1.25rem", borderBottom: `1px solid ${C.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1rem" }}>⬡</div>
            <span style={{ fontWeight: 700, fontSize: "1.05rem", letterSpacing: "-0.02em" }}>TokenWatch</span>
          </div>
        </div>

        <nav style={{ flex: 1, padding: "0.75rem 0.5rem" }}>
          {NAV_ITEMS.map(({ id, icon, label }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: "0.75rem",
                padding: "0.6rem 0.75rem", border: "none", borderRadius: 8, cursor: "pointer",
                background: page === id ? C.accentDim : "transparent",
                color: page === id ? C.accentLight : C.subtle,
                fontSize: "0.9rem", fontWeight: page === id ? 600 : 400,
                marginBottom: 2, transition: "all 0.15s",
              }}
            >
              <span style={{ fontSize: "0.8rem" }}>{icon}</span>
              {label}
            </button>
          ))}
        </nav>

        <div style={{ padding: "1rem 1.25rem", borderTop: `1px solid ${C.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: onLogout ? "0.6rem" : 0 }}>
            <div style={{ width: 32, height: 32, borderRadius: "50%", background: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.85rem", fontWeight: 700, flexShrink: 0 }}>
              {(user?.full_name ?? user?.email ?? "?")[0].toUpperCase()}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.full_name ?? user?.email ?? "User"}
              </div>
              <div style={{ fontSize: "0.75rem", color: C.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user?.email ?? ""}
              </div>
            </div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              style={{ width: "100%", background: "transparent", border: `1px solid ${C.border}`, color: C.muted, borderRadius: 8, padding: "0.4rem", fontSize: "0.8rem", cursor: "pointer" }}
            >
              Sign out
            </button>
          )}
        </div>
      </aside>

      {/* ── Main ── */}
      <main style={{ flex: 1, overflow: "auto", display: "flex", flexDirection: "column" }}>
        <header style={{ padding: "1.25rem 2rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", background: C.surface, flexShrink: 0 }}>
          <h1 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600 }}>
            {NAV_ITEMS.find(n => n.id === page)?.label}
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <select
              value={range}
              onChange={e => setRange(e.target.value)}
              style={{ background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.4rem 0.75rem", fontSize: "0.85rem", cursor: "pointer" }}
            >
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
            </select>
            <Pill color={C.green}>● Live</Pill>
          </div>
        </header>

        <div style={{ flex: 1, padding: "1.75rem 2rem", overflow: "auto" }}>
          {page === "overview" && (
            <OverviewPage summary={summary} records={records} timeseries={timeseries} breakdown={breakdown} dashSummary={dashSummary} loading={isLoading} />
          )}
          {page === "usage" && <UsagePage summary={summary} records={records} loading={isLoading} />}
          {page === "settings" && <SettingsPage quota={quota} />}
        </div>
      </main>
    </div>
  );
}

// ─── Overview ─────────────────────────────────────────────────────────────────
function OverviewPage({ summary, records, timeseries, breakdown, dashSummary, loading }: {
  summary: ApiCallSummary[];
  records: ApiCall[];
  timeseries: TimeseriesPoint[];
  breakdown: BreakdownRow[];
  dashSummary: { total_tokens_in: number; total_tokens_out: number; total_cost_usd: number; request_count: number; avg_latency_ms: number } | undefined;
  loading: boolean;
}) {
  const providerPie = Object.entries(
    breakdown.reduce<Record<string, number>>((acc, r) => {
      acc[r.provider] = (acc[r.provider] ?? 0) + r.cost_usd;
      return acc;
    }, {})
  ).map(([name, value]) => ({ name, value }));

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        <KpiCard label="Total Spend" value={loading ? "—" : fmtCost(dashSummary?.total_cost_usd ?? 0)} />
        <KpiCard label="Total Tokens" value={loading ? "—" : fmtNum((dashSummary?.total_tokens_in ?? 0) + (dashSummary?.total_tokens_out ?? 0))} />
        <KpiCard label="API Calls" value={loading ? "—" : fmtNum(dashSummary?.request_count ?? 0)} />
        <KpiCard label="Avg Latency" value={loading ? "—" : `${(dashSummary?.avg_latency_ms ?? 0).toFixed(0)}ms`} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        <Card title="Spend over time" subtitle="USD per period">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={timeseries}>
              <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.muted, fontSize: 12 }} axisLine={false} tickLine={false} tickFormatter={v => fmtCost(v)} />
              <Tooltip
                contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text }}
                formatter={(v: number) => [fmtCost(v), "Cost"]}
              />
              <Line type="monotone" dataKey="cost_usd" stroke={C.accent} strokeWidth={2.5} dot={false} name="Cost" />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Cost by provider" subtitle="% share">
          {providerPie.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={providerPie} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3}>
                  {providerPie.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Pie>
                <Tooltip
                  contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text }}
                  formatter={(v: number) => [fmtCost(v), "Cost"]}
                />
                <Legend iconType="circle" iconSize={8} formatter={v => <span style={{ color: C.subtle, fontSize: 12 }}>{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState label="No data yet" />
          )}
        </Card>
      </div>

      <div style={{ marginBottom: "1.5rem" }}>
        <Card title="Cost by model" subtitle="USD total">
          {breakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={breakdown} barSize={28}>
                <XAxis dataKey="model" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => fmtCost(v)} />
                <Tooltip
                  contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text }}
                  formatter={(v: number) => [fmtCost(v), "Cost"]}
                />
                <Bar dataKey="cost_usd" fill={C.accent} radius={[4, 4, 0, 0]} name="Cost (USD)" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState label="No model data yet" />
          )}
        </Card>
      </div>

      <Card title="Recent requests" subtitle={`${records.length} total`}>
        <RequestsTable records={records.slice(0, 10)} />
      </Card>
    </div>
  );
}

// ─── Usage ────────────────────────────────────────────────────────────────────
function UsagePage({ summary, records, loading }: { summary: ApiCallSummary[]; records: ApiCall[]; loading: boolean }) {
  const [filterProvider, setFilterProvider] = useState("all");
  const providers = ["all", ...Array.from(new Set(records.map(r => r.provider)))];
  const filtered = filterProvider === "all" ? records : records.filter(r => r.provider === filterProvider);

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        {summary.map(s => (
          <Card key={`${s.provider}-${s.model}`} title={s.model} subtitle={s.provider}>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.5rem" }}>
              <Metric label="Requests" value={fmtNum(s.request_count)} />
              <Metric label="In tokens" value={fmtNum(s.total_tokens_in)} />
              <Metric label="Out tokens" value={fmtNum(s.total_tokens_out)} />
              <Metric label="Cost" value={fmtCost(s.total_cost_usd)} accent />
            </div>
          </Card>
        ))}
        {summary.length === 0 && !loading && (
          <div style={{ gridColumn: "1/-1" }}>
            <EmptyState label="No usage recorded yet. Log your first API call to see stats here." />
          </div>
        )}
      </div>

      <Card
        title="All requests"
        subtitle={`${filtered.length} records`}
        action={
          <select
            value={filterProvider}
            onChange={e => setFilterProvider(e.target.value)}
            style={{ background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.35rem 0.6rem", fontSize: "0.8rem", cursor: "pointer" }}
          >
            {providers.map(p => <option key={p} value={p}>{p === "all" ? "All providers" : p}</option>)}
          </select>
        }
      >
        <RequestsTable records={filtered} />
      </Card>
    </div>
  );
}

// ─── API Keys ─────────────────────────────────────────────────────────────────

// ─── Settings ─────────────────────────────────────────────────────────────────
function SettingsPage({ quota }: { quota: { limit: number; used: number; remaining: number; reset_at: number; window_ms: number } | undefined }) {
  const pct = quota ? Math.round((quota.used / quota.limit) * 100) : 0;
  const resetAt = quota ? new Date(quota.reset_at).toLocaleTimeString() : "—";
  const [sdkToken, setSdkToken] = useState<string | null>(null);
  const [sdkCopied, setSdkCopied] = useState(false);
  const [sdkLoading, setSdkLoading] = useState(false);

  // Auto-load existing token on mount
  useState(() => { fetchSdkToken().then(r => setSdkToken(r.sdk_token)).catch(() => {}); });

  async function handleRegenerate() {
    if (!confirm("Regenerate SDK token? Your old token will stop working.")) return;
    setSdkLoading(true);
    try {
      const res = await regenerateSdkToken();
      setSdkToken(res.sdk_token);
    } finally {
      setSdkLoading(false);
    }
  }

  function handleCopy() {
    if (!sdkToken) return;
    navigator.clipboard.writeText(sdkToken);
    setSdkCopied(true);
    setTimeout(() => setSdkCopied(false), 2000);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: 560 }}>
      <Card title="SDK Token" subtitle="Use this token with the tokenwatch-sdk package (valid 1 year)">
        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <p style={{ margin: 0, fontSize: "0.85rem", color: C.subtle }}>
            Install: <code style={{ background: C.bg, padding: "2px 6px", borderRadius: 4 }}>pip install tokenwatch-sdk</code>
          </p>
          {sdkToken && (
            <div style={{ fontFamily: "monospace", fontSize: "0.78rem", background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.6rem 0.8rem", wordBreak: "break-all", color: C.subtle }}>
              {sdkToken}
            </div>
          )}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={handleCopy} disabled={!sdkToken} style={{ ...btnStyle(sdkCopied ? C.green : C.accent) }}>
              {sdkCopied ? "Copied!" : "Copy token"}
            </button>
            <button onClick={handleRegenerate} disabled={sdkLoading} style={{ ...btnStyle(C.muted) }}>
              {sdkLoading ? "Rotating…" : "Regenerate"}
            </button>
          </div>
          <p style={{ margin: 0, fontSize: "0.8rem", color: C.muted }}>
            Use the same token across all your projects — tag them with <code style={{ background: C.bg, padding: "2px 4px", borderRadius: 3 }}>app_tag</code> to tell them apart.
          </p>
        </div>
      </Card>

      <Card title="Rate limit quota" subtitle={`Resets at ${resetAt}`}>
        <div style={{ marginTop: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem", marginBottom: "0.4rem" }}>
            <span style={{ color: C.subtle }}>{fmtNum(quota?.used ?? 0)} used</span>
            <span style={{ color: C.muted }}>{fmtNum(quota?.limit ?? 0)} limit</span>
          </div>
          <div style={{ height: 8, background: C.border, borderRadius: 4, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${pct}%`, background: pct > 80 ? C.red : pct > 60 ? C.yellow : C.accent, borderRadius: 4, transition: "width 0.4s" }} />
          </div>
          <div style={{ fontSize: "0.8rem", color: C.muted, marginTop: "0.4rem" }}>{pct}% used · {fmtNum(quota?.remaining ?? 0)} remaining</div>
        </div>
      </Card>

      <Card title="Rate limits" subtitle="Set monthly token budgets per user">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <LabeledInput label="Monthly token limit" defaultValue="5000000" />
          <LabeledInput label="Daily token limit" defaultValue="500000" />
          <LabeledInput label="Alert threshold (%)" defaultValue="80" />
          <button style={{ ...btnStyle(C.accent), alignSelf: "flex-start", marginTop: "0.25rem" }}>Save limits</button>
        </div>
      </Card>

      <Card title="Alerts" subtitle="SMS alerts via Twilio when quotas are hit">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <LabeledInput label="Phone number" placeholder="+1 555 000 0000" />
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input type="checkbox" id="sms-toggle" defaultChecked style={{ accentColor: C.accent }} />
            <label htmlFor="sms-toggle" style={{ fontSize: "0.9rem", color: C.subtle }}>Enable SMS alerts at 80% / 100% quota</label>
          </div>
          <button style={{ ...btnStyle(C.accent), alignSelf: "flex-start" }}>Save alert settings</button>
        </div>
      </Card>

      <Card title="Danger zone" subtitle="Irreversible actions">
        <div style={{ marginTop: "0.75rem" }}>
          <button style={btnStyle(C.red)}>Delete all usage records</button>
        </div>
      </Card>
    </div>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────
function RequestsTable({ records }: { records: ApiCall[] }) {
  if (records.length === 0) return <EmptyState label="No requests yet." />;
  return (
    <div style={{ overflowX: "auto", marginTop: "0.5rem" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
        <thead>
          <tr>
            {["Time", "Provider", "Model", "App Tag", "In", "Out", "Latency", "Cost"].map(h => (
              <th key={h} style={{ textAlign: "left", padding: "0.5rem 0.75rem", color: C.muted, fontSize: "0.8rem", fontWeight: 500, borderBottom: `1px solid ${C.border}`, whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map(r => (
            <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
              <td style={tdStyle}>{new Date(r.timestamp).toLocaleString()}</td>
              <td style={tdStyle}><ProviderBadge provider={r.provider} small /></td>
              <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: "0.8rem" }}>{r.model}</td>
              <td style={{ ...tdStyle, color: C.muted }}>{r.app_tag ?? "—"}</td>
              <td style={tdStyle}>{r.tokens_in.toLocaleString()}</td>
              <td style={tdStyle}>{r.tokens_out.toLocaleString()}</td>
              <td style={{ ...tdStyle, color: C.subtle }}>{r.latency_ms}ms</td>
              <td style={{ ...tdStyle, color: C.accentLight, fontWeight: 600 }}>{fmtCost(r.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem 1.5rem" }}>
      <div style={{ color: C.muted, fontSize: "0.8rem", marginBottom: "0.5rem" }}>{label}</div>
      <div style={{ fontSize: "1.75rem", fontWeight: 700, letterSpacing: "-0.03em" }}>{value}</div>
    </div>
  );
}

function Card({ title, subtitle, children, action }: { title: string; subtitle?: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem 1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{title}</div>
          {subtitle && <div style={{ color: C.muted, fontSize: "0.8rem", marginTop: 2 }}>{subtitle}</div>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div style={{ color: C.muted, fontSize: "0.75rem" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: "0.95rem", color: accent ? C.accentLight : C.text }}>{value}</div>
    </div>
  );
}

function Pill({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span style={{ background: `${color}22`, color, borderRadius: 6, padding: "0.2rem 0.55rem", fontSize: "0.75rem", fontWeight: 600, whiteSpace: "nowrap" }}>
      {children}
    </span>
  );
}

function ProviderBadge({ provider, small }: { provider: string; small?: boolean }) {
  const color = PROVIDER_COLORS[provider] ?? C.muted;
  return (
    <span style={{ background: `${color}22`, color, borderRadius: 6, padding: small ? "0.15rem 0.4rem" : "0.3rem 0.65rem", fontSize: small ? "0.75rem" : "0.8rem", fontWeight: 600 }}>
      {provider}
    </span>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div style={{ textAlign: "center", padding: "2.5rem 1rem", color: C.muted, fontSize: "0.9rem" }}>
      <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>◌</div>
      {label}
    </div>
  );
}

function LabeledInput({ label, defaultValue, placeholder }: { label: string; defaultValue?: string; placeholder?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <label style={{ fontSize: "0.82rem", color: C.subtle }}>{label}</label>
      <input
        defaultValue={defaultValue}
        placeholder={placeholder}
        style={{ background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.5rem 0.75rem", fontSize: "0.9rem" }}
      />
    </div>
  );
}

function btnStyle(color: string): React.CSSProperties {
  return { background: color, color: "#fff", border: "none", borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 };
}

const tdStyle: React.CSSProperties = { padding: "0.6rem 0.75rem", verticalAlign: "middle" };

function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function fmtCost(v: number): string {
  if (v === 0) return "$0.00";
  const s = v.toPrecision(20).replace(/\.?0+$/, "");
  const [int, dec] = s.split(".");
  if (!dec) return `$${int}.00`;
  const trimmed = dec.length <= 2 ? dec.padEnd(2, "0") : dec;
  return `$${int}.${trimmed}`;
}
