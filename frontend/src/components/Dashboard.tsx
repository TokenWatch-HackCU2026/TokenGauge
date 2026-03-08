import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  fetchRecords, fetchSummary, fetchDashboardSummary,
  fetchBreakdown, fetchQuota,
  fetchSdkToken, regenerateSdkToken, recalculateCosts, updatePhone,
  ApiCall, ApiCallSummary, BreakdownRow, UserOut,
} from "../api/client";
import { C, PROVIDER_COLORS, PIE_COLORS, LINE_COLORS, GaugeLogo } from "../theme";

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
            <GaugeLogo size={32} />
            <span style={{ fontWeight: 700, fontSize: "1.05rem", letterSpacing: "-0.02em" }}>TokenGauge</span>
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
            <OverviewPage summary={summary} records={records} breakdown={breakdown} dashSummary={dashSummary} loading={isLoading} range={range} />
          )}
          {page === "usage" && <UsagePage summary={summary} records={records} loading={isLoading} />}
          {page === "settings" && <SettingsPage quota={quota} user={user} />}
        </div>
      </main>
    </div>
  );
}

// ─── Chart helpers ─────────────────────────────────────────────────────────────

function bucketKey(ts: string, range: string): string {
  const d = new Date(ts);
  if (range === "24h") {
    return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:00`;
  }
  return `${d.getMonth()+1}/${d.getDate()}`;
}

// ─── Model Usage Histogram (stacked bar) ─────────────────────────────────────
type UsageMetric = "cost" | "requests" | "tokens";

function ModelUsageChart({ records, range }: { records: ApiCall[]; range: string }) {
  const [metric, setMetric] = useState<UsageMetric>("cost");
  const [selected, setSelected] = useState<string | null>(null);

  // Bucket records by date × model
  const buckets: Record<string, Record<string, number>> = {};
  const models = new Set<string>();
  for (const r of records) {
    const bk = bucketKey(r.timestamp, range);
    models.add(r.model);
    if (!buckets[bk]) buckets[bk] = {};
    const val = metric === "cost" ? r.cost_usd : metric === "requests" ? 1 : r.tokens_in + r.tokens_out;
    buckets[bk][r.model] = (buckets[bk][r.model] ?? 0) + val;
  }
  const sortedBuckets = Object.keys(buckets).sort();
  const data = sortedBuckets.map(bk => ({ date: bk, ...buckets[bk] }));
  const modelList = Array.from(models);

  const subtitles: Record<UsageMetric, string> = { cost: "USD per period", requests: "Requests per period", tokens: "Tokens per period" };

  const toggleBtn = (label: string, val: UsageMetric) => (
    <button
      key={val}
      onClick={() => setMetric(val)}
      style={{ background: metric === val ? C.accent : C.border, color: metric === val ? "#fff" : C.muted, border: "none", borderRadius: 6, padding: "0.25rem 0.65rem", fontSize: "0.75rem", fontWeight: 600, cursor: "pointer" }}
    >
      {label}
    </button>
  );

  const fmtValue = (v: number) => metric === "cost" ? fmtCost(v) : fmtNum(v);

  return (
    <Card
      title="Model usage over time"
      subtitle={subtitles[metric]}
      action={<div style={{ display: "flex", gap: 4 }}>{toggleBtn("Cost","cost")}{toggleBtn("Requests","requests")}{toggleBtn("Tokens","tokens")}</div>}
    >
      {data.length === 0 ? <EmptyState label="No data for this period" /> : (
        <>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data}>
              <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={fmtValue} width={70} />
              <Tooltip
                contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text }}
                formatter={(v: number, name: string) => [fmtValue(v), name]}
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
              />
              {modelList.map((model, i) => (
                <Bar
                  key={model}
                  dataKey={model}
                  stackId="models"
                  fill={LINE_COLORS[i % LINE_COLORS.length]}
                  fillOpacity={selected === null || selected === model ? 0.9 : 0.15}
                  radius={i === modelList.length - 1 ? [4, 4, 0, 0] : undefined}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem 0.75rem", marginTop: "0.5rem" }}>
            {modelList.map((model, i) => (
              <button key={model} onClick={() => setSelected(selected === model ? null : model)} style={{ background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 5, padding: "2px 4px", borderRadius: 4, opacity: selected === null || selected === model ? 1 : 0.35 }}>
                <span style={{ width: 10, height: 10, borderRadius: "50%", background: LINE_COLORS[i % LINE_COLORS.length], display: "inline-block", flexShrink: 0 }} />
                <span style={{ fontSize: "0.78rem", color: C.subtle }}>{model}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

// ─── Cost breakdown pie ────────────────────────────────────────────────────────
function CostPieChart({ breakdown }: { breakdown: BreakdownRow[] }) {
  const pieData = Object.entries(
    breakdown.reduce<Record<string, number>>((acc, r) => { acc[r.model] = (acc[r.model] ?? 0) + r.cost_usd; return acc; }, {})
  ).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);

  return (
    <Card title="Cost by model" subtitle="% share">
      {pieData.length > 0 ? (
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3}>
              {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, color: C.text }} formatter={(v: number) => [fmtCost(v), "Cost"]} />
            <Legend iconType="circle" iconSize={8} formatter={v => <span style={{ color: C.subtle, fontSize: 12 }}>{v}</span>} />
          </PieChart>
        </ResponsiveContainer>
      ) : (
        <EmptyState label="No data yet" />
      )}
    </Card>
  );
}

// ─── Overview ─────────────────────────────────────────────────────────────────
function OverviewPage({ summary, records, breakdown, dashSummary, loading, range }: {
  summary: ApiCallSummary[];
  records: ApiCall[];
  breakdown: BreakdownRow[];
  dashSummary: { total_tokens_in: number; total_tokens_out: number; total_cost_usd: number; request_count: number; avg_latency_ms: number } | undefined;
  loading: boolean;
  range: string;
}) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        <KpiCard label="Total Spend" value={loading ? "—" : fmtCost(dashSummary?.total_cost_usd ?? 0)} />
        <KpiCard label="Total Tokens" value={loading ? "—" : fmtNum((dashSummary?.total_tokens_in ?? 0) + (dashSummary?.total_tokens_out ?? 0))} />
        <KpiCard label="API Calls" value={loading ? "—" : fmtNum(dashSummary?.request_count ?? 0)} />
        <KpiCard label="Avg Latency" value={loading ? "—" : `${(dashSummary?.avg_latency_ms ?? 0).toFixed(0)}ms`} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        <ModelUsageChart records={records} range={range} />
        <CostPieChart breakdown={breakdown} />
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
function SettingsPage({ quota, user }: { quota: { limit: number; used: number; remaining: number; reset_at: number; window_ms: number } | undefined; user?: UserOut | null }) {
  const pct = quota ? Math.round((quota.used / quota.limit) * 100) : 0;
  const resetAt = quota ? new Date(quota.reset_at).toLocaleTimeString() : "—";
  const [sdkToken, setSdkToken] = useState<string | null>(null);
  const [sdkCopied, setSdkCopied] = useState(false);
  const [sdkLoading, setSdkLoading] = useState(false);
  const [recalcLoading, setRecalcLoading] = useState(false);
  const [recalcMsg, setRecalcMsg] = useState<string | null>(null);
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [phoneSaving, setPhoneSaving] = useState(false);
  const [phoneMsg, setPhoneMsg] = useState<string | null>(null);

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

  async function handleRecalculate() {
    setRecalcLoading(true);
    setRecalcMsg(null);
    try {
      const res = await recalculateCosts();
      setRecalcMsg(`Updated ${res.recalculated} record${res.recalculated !== 1 ? "s" : ""}`);
    } catch {
      setRecalcMsg("Failed — try again");
    } finally {
      setRecalcLoading(false);
    }
  }

  async function handlePhoneSave() {
    setPhoneMsg(null);
    const trimmed = phone.replace(/\s/g, "");
    if (!trimmed) {
      setPhoneMsg("Please enter a phone number");
      return;
    }
    if (!/^\+[1-9]\d{1,14}$/.test(trimmed)) {
      setPhoneMsg("Use E.164 format (e.g. +15551234567)");
      return;
    }
    setPhoneSaving(true);
    try {
      await updatePhone(trimmed);
      setPhone(trimmed);
      setPhoneMsg("Saved!");
      setTimeout(() => setPhoneMsg(null), 3000);
    } catch (err) {
      setPhoneMsg(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setPhoneSaving(false);
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
      <Card title="SDK Token" subtitle="Use this token with the tokengauge-sdk package (valid 1 year)">
        <div style={{ marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          <p style={{ margin: 0, fontSize: "0.85rem", color: C.subtle }}>
            Install: <code style={{ background: C.bg, padding: "2px 6px", borderRadius: 4 }}>pip install tokengauge-sdk</code>
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

      <Card title="Fix $0.00 costs" subtitle="Recalculates cost for records that logged as $0.00 due to unrecognized model names">
        <div style={{ marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <button onClick={handleRecalculate} disabled={recalcLoading} style={{ ...btnStyle(C.accent) }}>
            {recalcLoading ? "Recalculating…" : "Recalculate costs"}
          </button>
          {recalcMsg && <span style={{ fontSize: "0.85rem", color: C.subtle }}>{recalcMsg}</span>}
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

      <Card title="SMS Alerts" subtitle="Get texted when you hit 80% or 100% of your daily token quota">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label style={{ fontSize: "0.82rem", color: C.subtle }}>Phone number (E.164 format)</label>
            <input
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+15551234567"
              style={{ background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.5rem 0.75rem", fontSize: "0.9rem" }}
            />
          </div>
          <p style={{ margin: 0, fontSize: "0.8rem", color: C.muted }}>
            You'll receive an SMS when your daily token usage crosses 80% and 100% of the {fmtNum(quota?.limit ?? 1_000_000)} token quota.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <button onClick={handlePhoneSave} disabled={phoneSaving} style={{ ...btnStyle(C.accent) }}>
              {phoneSaving ? "Saving…" : "Save phone number"}
            </button>
            {phoneMsg && (
              <span style={{ fontSize: "0.85rem", color: phoneMsg === "Saved!" ? C.green : C.red }}>
                {phoneMsg}
              </span>
            )}
          </div>
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
            {["Time", "Provider", "Model", "App Tag", "Key", "In", "Out", "Latency", "Cost"].map(h => (
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
              <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: "0.78rem", color: C.muted }}>{r.key_hint ? `…${r.key_hint}` : "—"}</td>
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
  if (v >= 1) return `$${v.toFixed(2)}`;
  if (v >= 0.01) return `$${v.toFixed(4)}`;
  const decimals = -Math.floor(Math.log10(v)) + 1;
  return `~$${v.toFixed(decimals)}`;
}
