import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ComposedChart, Area, Line,
} from "recharts";
import {
  fetchRecords, fetchSummary, fetchDashboardSummary,
  fetchQuota,
  fetchSdkToken, regenerateSdkToken, recalculateCosts, updatePhone,
  ApiCall, ApiCallSummary, BreakdownRow, UserOut,
} from "../api/client";
import { C, PROVIDER_COLORS, LINE_COLORS, GaugeLogo } from "../theme";
import { saveCache, loadCache } from "../api/cache";

// ─── SVG Icons ───────────────────────────────────────────────────────────────
function IconMenu() {
  return <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="3" y1="5" x2="17" y2="5"/><line x1="3" y1="10" x2="17" y2="10"/><line x1="3" y1="15" x2="17" y2="15"/></svg>;
}
function IconClose() {
  return <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg>;
}
function IconOverview() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>;
}
function IconUsage() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="1,12 5,6 9,9 15,3"/><line x1="11" y1="3" x2="15" y2="3"/><line x1="15" y1="3" x2="15" y2="7"/></svg>;
}
function IconSettings() {
  return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="8" r="2.5"/><path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M2.8 2.8l1.1 1.1M12.1 12.1l1.1 1.1M13.2 2.8l-1.1 1.1M3.9 12.1l-1.1 1.1"/></svg>;
}
function IconEmpty() {
  return <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke={C.muted} strokeWidth="1.5" strokeLinecap="round"><circle cx="16" cy="16" r="12" strokeDasharray="4 3"/><line x1="16" y1="11" x2="16" y2="17"/><circle cx="16" cy="21" r="0.5" fill={C.muted}/></svg>;
}

// ─── Date range helpers ───────────────────────────────────────────────────────
type Range = "live" | "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y" | "ALL";
const RANGES: Range[] = ["live", "1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"];

function rangeToParams(range: Range) {
  const now = new Date();
  const ms: Record<Range, number | null> = {
    live: 3_600_000,
    "1D": 86_400_000,
    "1W": 7 * 86_400_000,
    "1M": 30 * 86_400_000,
    "3M": 90 * 86_400_000,
    YTD: now.getTime() - new Date(now.getFullYear(), 0, 1).getTime(),
    "1Y": 365 * 86_400_000,
    ALL: null,
  };
  const offset = ms[range];
  if (offset === null) return {};
  return { startDate: new Date(now.getTime() - offset).toISOString(), endDate: now.toISOString() };
}

// Auto-pick chart granularity from range — fine intervals for smooth scrubbing
function rangeToGranularity(range: Range): Granularity {
  switch (range) {
    case "live":  return "15s";
    case "1D":    return "15min";
    case "1W":    return "1hr";
    case "1M":    return "4hr";
    case "3M":    return "12hr";
    case "YTD": case "1Y": return "1day";
    case "ALL":   return "1week";
  }
}

// ─── Responsive hook ─────────────────────────────────────────────────────────
function useIsMobile(breakpoint = 768) {
  const [mobile, setMobile] = useState(() => typeof window !== "undefined" && window.innerWidth < breakpoint);
  useEffect(() => {
    const check = () => setMobile(window.innerWidth < breakpoint);
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, [breakpoint]);
  return mobile;
}

// ─── Types ────────────────────────────────────────────────────────────────────
type Page = "overview" | "usage" | "settings";

const NAV_ITEMS: { id: Page; icon: React.ReactNode; label: string }[] = [
  { id: "overview", icon: <IconOverview />, label: "Overview" },
  { id: "usage", icon: <IconUsage />, label: "Usage" },
  { id: "settings", icon: <IconSettings />, label: "Settings" },
];

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function Dashboard({ onLogout, user }: { onLogout?: () => void; user?: UserOut | null }) {
  const mobile = useIsMobile();
  const [page, setPage] = useState<Page>("overview");
  const [range, setRange] = useState<Range>("1W");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [filters, setFilters] = useState<{ provider: string; appTag: string; keyHint: string }>({ provider: "all", appTag: "all", keyHint: "all" });
  const params = rangeToParams(range);
  const gran = rangeToGranularity(range);

  // Escape key closes mobile sidebar
  useEffect(() => {
    if (!sidebarOpen) return;
    const handleKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSidebarOpen(false); };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [sidebarOpen]);

  const { data: dashSummary } = useQuery({
    queryKey: ["dashboard-summary", range],
    queryFn: () => fetchDashboardSummary(params),
  });
  const { data: summary = [] } = useQuery({
    queryKey: ["summary"],
    queryFn: fetchSummary,
  });
  const { data: records = [], isLoading } = useQuery({
    queryKey: ["records"],
    queryFn: () => fetchRecords(100),
    refetchInterval: 3000,
    placeholderData: () => loadCache<ApiCall[]>("records") ?? [],
  });
  useEffect(() => { if (records.length > 0) saveCache("records", records); }, [records]);
  const { data: quota } = useQuery({
    queryKey: ["quota"],
    queryFn: fetchQuota,
  });

  // ── Global client-side filtering ──────────────────────────────────────────
  const filterOptions = useMemo(() => ({
    providers: Array.from(new Set(records.map(r => r.provider))).sort(),
    appTags: Array.from(new Set(records.map(r => r.app_tag).filter(Boolean) as string[])).sort(),
    keyHints: Array.from(new Set(records.map(r => r.key_hint).filter(Boolean) as string[])).sort(),
  }), [records]);

  const filteredRecords = useMemo(() => {
    let result = records;
    if (filters.provider !== "all") result = result.filter(r => r.provider === filters.provider);
    if (filters.appTag !== "all") result = result.filter(r => r.app_tag === filters.appTag);
    if (filters.keyHint !== "all") result = result.filter(r => r.key_hint === filters.keyHint);
    return result;
  }, [records, filters]);

  const hasActiveFilter = filters.provider !== "all" || filters.appTag !== "all" || filters.keyHint !== "all";

  // Track last time records were refreshed + rolling "ago" label
  const lastUpdatedRef = useRef<number>(Date.now());
  const [agoText, setAgoText] = useState("just now");
  useEffect(() => {
    if (records.length > 0 || !isLoading) lastUpdatedRef.current = Date.now();
  }, [records, isLoading]);
  useEffect(() => {
    const tick = () => {
      const sec = Math.floor((Date.now() - lastUpdatedRef.current) / 1000);
      if (sec < 5) setAgoText("just now");
      else if (sec < 60) setAgoText(`${sec}s ago`);
      else if (sec < 3600) setAgoText(`${Math.floor(sec / 60)}m ago`);
      else setAgoText(`${Math.floor(sec / 3600)}h ago`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const sidebar = (
    <aside style={{
      width: mobile ? "75vw" : 220,
      maxWidth: 280,
      background: C.surface,
      borderRight: `1px solid ${C.border}`,
      display: "flex",
      flexDirection: "column",
      flexShrink: 0,
      ...(mobile ? { height: "100%" } : {}),
    }}>
      <div style={{ padding: "1.5rem 1.25rem 1.25rem", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          <GaugeLogo size={32} />
          <span style={{ fontWeight: 700, fontSize: "1.05rem", letterSpacing: "-0.02em" }}>TokenGauge</span>
        </div>
        {mobile && (
          <button onClick={() => setSidebarOpen(false)} aria-label="Close sidebar" style={{ background: "none", border: "none", color: C.muted, cursor: "pointer", padding: 4, display: "flex", alignItems: "center" }}><IconClose /></button>
        )}
      </div>

      <nav style={{ flex: 1, padding: "0.75rem 0.5rem" }} aria-label="Main navigation">
        {NAV_ITEMS.map(({ id, icon, label }) => (
          <button
            key={id}
            onClick={() => { setPage(id); if (mobile) setSidebarOpen(false); }}
            aria-current={page === id ? "page" : undefined}
            style={{
              width: "100%", display: "flex", alignItems: "center", gap: "0.75rem",
              padding: "0.6rem 0.75rem", border: "none", borderRadius: 8, cursor: "pointer",
              background: page === id ? C.accentDim : "transparent",
              color: page === id ? C.accentLight : C.subtle,
              fontSize: "0.9rem", fontWeight: page === id ? 600 : 400,
              marginBottom: 2, transition: "all 0.15s",
            }}
          >
            <span aria-hidden="true" style={{ display: "flex", alignItems: "center" }}>{icon}</span>
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
  );

  return (
    <div style={{ display: "flex", height: "100vh", background: C.bg, color: C.text, fontFamily: "'Inter', system-ui, sans-serif", overflow: "hidden" }}>
      {/* ── Sidebar ── */}
      {mobile ? (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setSidebarOpen(false)}
            style={{
              position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 99,
              opacity: sidebarOpen ? 1 : 0,
              pointerEvents: sidebarOpen ? "auto" : "none",
              transition: "opacity 0.2s ease",
            }}
          />
          {/* Sliding sidebar panel */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            style={{
              position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 100,
              transform: sidebarOpen ? "translateX(0)" : "translateX(-100%)",
              transition: "transform 0.25s ease",
            }}
          >
            {sidebar}
          </div>
        </>
      ) : sidebar}

      {/* ── Main ── */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        <header style={{
          padding: mobile ? "0.75rem 1rem" : "1.25rem 2rem",
          borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: C.surface, flexShrink: 0, gap: "0.5rem",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {mobile && (
              <button onClick={() => setSidebarOpen(true)} aria-label="Open menu" style={{ background: "none", border: "none", color: C.text, cursor: "pointer", padding: 2, display: "flex", alignItems: "center" }}><IconMenu /></button>
            )}
            <h1 style={{ margin: 0, fontSize: mobile ? "1rem" : "1.15rem", fontWeight: 600, whiteSpace: "nowrap" }}>
              {NAV_ITEMS.find(n => n.id === page)?.label}
            </h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexShrink: 1, minWidth: 0 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 2, background: C.bg, borderRadius: 8, padding: 3,
              overflowX: "auto", flexShrink: 1, minWidth: 0,
            }}>
              {RANGES.map(r => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  style={{
                    background: range === r ? C.accent : "transparent",
                    color: range === r ? C.onAccent : C.muted,
                    border: "none",
                    borderRadius: 6,
                    padding: mobile ? "0.5rem 0.6rem" : "0.35rem 0.7rem",
                    fontSize: mobile ? "0.72rem" : "0.78rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    transition: "all 0.12s",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {r === "live" ? "Live" : r}
                </button>
              ))}
            </div>
            {!mobile && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Pill color={C.green}>● Live</Pill>
                <span style={{ fontSize: "0.72rem", color: C.muted, whiteSpace: "nowrap" }}>
                  {agoText}
                </span>
              </div>
            )}
          </div>
        </header>

        {/* ── Filter bar ── */}
        {page !== "settings" && (
          <FilterBar
            filters={filters}
            onChange={setFilters}
            options={filterOptions}
            hasActive={hasActiveFilter}
            mobile={mobile}
          />
        )}

        <div style={{ flex: 1, padding: mobile ? "1rem" : "1.75rem 2rem", overflow: "auto" }}>
          {page === "overview" && (
            <OverviewPage summary={summary} records={filteredRecords} dashSummary={dashSummary} loading={isLoading} gran={gran} range={range} mobile={mobile} />
          )}
          {page === "usage" && <UsagePage summary={summary} records={filteredRecords} loading={isLoading} mobile={mobile} />}
          {page === "settings" && <SettingsPage quota={quota} user={user} mobile={mobile} />}
        </div>
      </main>
    </div>
  );
}

// ─── Chart helpers ─────────────────────────────────────────────────────────────

type Granularity = "15s" | "15min" | "1hr" | "4hr" | "12hr" | "1day" | "1week";
const pad2 = (n: number) => String(n).padStart(2, "0");

// Returns { sort: sortable key, label: display label } in browser local time
function bucketInfoFromDate(d: Date, gran: Granularity): { sort: string; label: string } {
  const Y = d.getFullYear(), M = d.getMonth(), D = d.getDate(), H = d.getHours(), min = d.getMinutes(), sec = d.getSeconds();
  const h12 = H % 12 || 12;
  const ampm = H >= 12 ? "PM" : "AM";

  switch (gran) {
    case "15s": {
      const s15 = Math.floor(sec / 15) * 15;
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}T${pad2(H)}:${pad2(min)}:${pad2(s15)}`, label: `${h12}:${pad2(min)}:${pad2(s15)} ${ampm}` };
    }
    case "15min": {
      const m15 = Math.floor(min / 15) * 15;
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}T${pad2(H)}:${pad2(m15)}`, label: `${h12}:${pad2(m15)} ${ampm}` };
    }
    case "1hr":
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}T${pad2(H)}`, label: `${d.toLocaleString("default", { weekday: "short" })} ${h12} ${ampm}` };
    case "4hr": {
      const h4 = Math.floor(H / 4) * 4;
      const h4_12 = h4 % 12 || 12;
      const ampm4 = h4 >= 12 ? "PM" : "AM";
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}T${pad2(h4)}`, label: `${M+1}/${D} ${h4_12} ${ampm4}` };
    }
    case "12hr": {
      const half = H < 12 ? "AM" : "PM";
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}T${half}`, label: `${M+1}/${D} ${half}` };
    }
    case "1day":
      return { sort: `${Y}-${pad2(M+1)}-${pad2(D)}`, label: `${d.toLocaleString("default", { weekday: "short" })} ${d.toLocaleString("default", { month: "short" })} ${D}` };
    case "1week": {
      const dow = d.getDay();
      const mon = new Date(d);
      mon.setDate(D - dow + (dow === 0 ? -6 : 1));
      const wY = mon.getFullYear(), wM = mon.getMonth(), wD = mon.getDate();
      return { sort: `${wY}-${pad2(wM+1)}-${pad2(wD)}`, label: `${mon.toLocaleString("default", { month: "short" })} ${wD}` };
    }
  }
}

// Parse timestamp as UTC if it lacks a timezone indicator, then convert to local
function parseTimestamp(ts: string): Date {
  if (/[Zz]|[+-]\d{2}:?\d{2}$/.test(ts)) return new Date(ts);
  return new Date(ts + "Z");
}

function bucketInfo(ts: string, gran: Granularity) {
  return bucketInfoFromDate(parseTimestamp(ts), gran);
}

// Generate every bucket in a range so the chart is continuous (zeros where no data)
function generateTimeline(range: Range, gran: Granularity): { sort: string; label: string }[] {
  const now = new Date();
  let start: Date;

  if (range === "ALL") {
    start = new Date(now);
    start.setMonth(start.getMonth() - 12);
  } else if (range === "YTD") {
    start = new Date(now.getFullYear(), 0, 1);
  } else {
    const msMap: Record<string, number> = {
      live: 3_600_000, "1D": 86_400_000, "1W": 7 * 86_400_000,
      "1M": 30 * 86_400_000, "3M": 90 * 86_400_000, "1Y": 365 * 86_400_000,
    };
    start = new Date(now.getTime() - (msMap[range] ?? 86_400_000));
  }

  const timeline: { sort: string; label: string }[] = [];
  const seen = new Set<string>();
  const cursor = new Date(start);

  // Align cursor to bucket boundary
  switch (gran) {
    case "15s":  cursor.setMilliseconds(0); cursor.setSeconds(Math.floor(cursor.getSeconds() / 15) * 15); break;
    case "15min": cursor.setSeconds(0, 0); cursor.setMinutes(Math.floor(cursor.getMinutes() / 15) * 15); break;
    case "1hr":  cursor.setMinutes(0, 0, 0); break;
    case "4hr":  cursor.setMinutes(0, 0, 0); cursor.setHours(Math.floor(cursor.getHours() / 4) * 4); break;
    case "12hr": cursor.setMinutes(0, 0, 0); cursor.setHours(cursor.getHours() < 12 ? 0 : 12); break;
    case "1day": cursor.setHours(0, 0, 0, 0); break;
    case "1week": {
      cursor.setHours(0, 0, 0, 0);
      const dow = cursor.getDay();
      cursor.setDate(cursor.getDate() - dow + (dow === 0 ? -6 : 1));
      break;
    }
  }

  while (cursor <= now) {
    const info = bucketInfoFromDate(cursor, gran);
    if (!seen.has(info.sort)) {
      seen.add(info.sort);
      timeline.push(info);
    }
    // Advance cursor
    switch (gran) {
      case "15s":  cursor.setSeconds(cursor.getSeconds() + 15); break;
      case "15min": cursor.setMinutes(cursor.getMinutes() + 15); break;
      case "1hr":  cursor.setHours(cursor.getHours() + 1); break;
      case "4hr":  cursor.setHours(cursor.getHours() + 4); break;
      case "12hr": cursor.setHours(cursor.getHours() + 12); break;
      case "1day": cursor.setDate(cursor.getDate() + 1); break;
      case "1week": cursor.setDate(cursor.getDate() + 7); break;
    }
  }
  return timeline;
}

// ─── Bar chart granularity (coarser than line charts) ────────────────────────
function rangeToBarGranularity(range: Range): Granularity {
  switch (range) {
    case "live":  return "15min";
    case "1D":    return "4hr";
    case "1W":    return "1day";
    case "1M":    return "1week";
    case "3M":    return "1week";
    case "YTD": case "1Y": return "1week";
    case "ALL":   return "1week";
  }
}

const MAX_GROUPED_BINS = 20;
const MAX_STACKED_BINS = 30;

// Build bar-chart-ready data from raw records
function buildBarData(
  records: ApiCall[],
  range: Range,
  metric: "cost" | "requests" | "tokens",
  maxBins: number,
): { data: Record<string, string | number>[]; models: string[] } {
  const gran = rangeToBarGranularity(range);
  const timeline = generateTimeline(range, gran);

  // Accumulate per-bucket per-model
  const filled: Record<string, Record<string, number>> = {};
  for (const { sort } of timeline) filled[sort] = {};

  const modelSet = new Set<string>();
  for (const r of records) {
    const { sort } = bucketInfo(r.timestamp, gran);
    modelSet.add(r.model);
    if (!filled[sort]) filled[sort] = {};
    const val = metric === "cost" ? r.cost_usd : metric === "requests" ? 1 : r.tokens_in + r.tokens_out;
    filled[sort][r.model] = (filled[sort][r.model] ?? 0) + val;
  }

  const models = Array.from(modelSet);

  // Build rows from timeline
  let rows = timeline.map(({ sort, label }) => {
    const row: Record<string, string | number> = { date: label };
    for (const m of models) row[m] = filled[sort]?.[m] ?? 0;
    return row;
  });

  // Merge adjacent bins if too many
  if (rows.length > maxBins) {
    const mergeN = Math.ceil(rows.length / maxBins);
    const merged: typeof rows = [];
    for (let i = 0; i < rows.length; i += mergeN) {
      const chunk = rows.slice(i, i + mergeN);
      const combined: Record<string, string | number> = {
        date: chunk.length === 1
          ? chunk[0].date
          : `${chunk[0].date} – ${chunk[chunk.length - 1].date}`,
      };
      for (const m of models) {
        combined[m] = chunk.reduce((s, r) => s + ((r[m] as number) ?? 0), 0);
      }
      merged.push(combined);
    }
    rows = merged;
  }

  return { data: rows, models };
}

// Normalize rows to 100% per bucket
function normalizeToPercent(
  data: Record<string, string | number>[],
  models: string[],
): Record<string, string | number>[] {
  return data.map(row => {
    const total = models.reduce((s, m) => s + ((row[m] as number) ?? 0), 0);
    const norm: Record<string, string | number> = { date: row.date };
    for (const m of models) {
      norm[m] = total > 0 ? ((row[m] as number) / total) * 100 : 0;
    }
    norm._total = total; // stash for tooltip
    return norm;
  });
}

// ─── Shared chart tooltip ────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function BarTooltip({ active, payload, label, fmtValue, showPercent, rawData }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
      padding: "0.6rem 0.85rem", boxShadow: "0 4px 20px rgba(0,0,0,0.4)",
      minWidth: 140,
    }}>
      <div style={{ fontSize: "0.75rem", color: C.muted, marginBottom: 6 }}>{label}</div>
      {payload
        .filter((p: { value: number }) => p.value > 0)
        .sort((a: { value: number }, b: { value: number }) => b.value - a.value)
        .map((p: { dataKey: string; value: number; color: string }) => (
          <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color, flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize: "0.78rem", color: C.subtle, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.dataKey}</span>
            <span style={{ fontSize: "0.78rem", fontWeight: 600, color: C.text, whiteSpace: "nowrap" }}>
              {showPercent ? `${p.value.toFixed(1)}%` : fmtValue(p.value)}
            </span>
          </div>
        ))}
      {showPercent && rawData && (
        <div style={{ borderTop: `1px solid ${C.border}`, marginTop: 4, paddingTop: 4, fontSize: "0.72rem", color: C.muted }}>
          Total: {fmtNum(rawData._total ?? 0)} tokens
        </div>
      )}
    </div>
  );
}

// ─── Shared chart legend ────────────────────────────────────────────────────
function ChartLegend({ models, selected, onSelect, totals, fmtValue }: {
  models: string[];
  selected: string | null;
  onSelect: (m: string | null) => void;
  totals?: Record<string, number>;
  fmtValue?: (v: number) => string;
}) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem 0.6rem", marginTop: "0.6rem" }}>
      {models.map((model, i) => {
        const active = selected === null || selected === model;
        return (
          <button
            key={model}
            onClick={() => onSelect(selected === model ? null : model)}
            style={{
              background: active ? `${LINE_COLORS[i % LINE_COLORS.length]}18` : "transparent",
              border: `1px solid ${active ? `${LINE_COLORS[i % LINE_COLORS.length]}40` : "transparent"}`,
              borderRadius: 6, cursor: "pointer", display: "flex", alignItems: "center",
              gap: 5, padding: "3px 8px",
              opacity: active ? 1 : 0.35, transition: "all 0.15s",
            }}
          >
            <span style={{ width: 8, height: 8, borderRadius: 2, background: LINE_COLORS[i % LINE_COLORS.length], flexShrink: 0 }} />
            <span style={{ fontSize: "0.75rem", color: C.subtle, whiteSpace: "nowrap" }}>{model}</span>
            {totals && fmtValue && (
              <span style={{ fontSize: "0.72rem", fontWeight: 600, color: C.text, marginLeft: 2 }}>{fmtValue(totals[model] ?? 0)}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ─── Cost Bar Chart (grouped) ───────────────────────────────────────────────
function CostBarChart({ records, range, mobile }: { records: ApiCall[]; range: Range; mobile: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const { data, models } = useMemo(() => buildBarData(records, range, "cost", MAX_GROUPED_BINS), [records, range]);
  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    for (const m of models) t[m] = data.reduce((s, r) => s + ((r[m] as number) ?? 0), 0);
    return t;
  }, [data, models]);
  const grandTotal = Object.values(totals).reduce((s, v) => s + v, 0);

  if (data.length === 0 || models.length === 0) {
    return (
      <div style={chartCardStyle}>
        <div style={chartTitleStyle}>Cost by Model</div>
        <EmptyState label="No cost data for this period" />
      </div>
    );
  }

  return (
    <div style={chartCardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
        <div>
          <div style={chartTitleStyle}>Cost by Model</div>
          <div style={{ color: C.muted, fontSize: "0.78rem" }}>Total: {fmtCost(grandTotal)}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={mobile ? 220 : 260}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap="20%" barGap={1}>
          <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => fmtCost(v)} width={50} scale="log" domain={['auto', 'auto']} allowDataOverflow />
          <Tooltip content={<BarTooltip fmtValue={fmtCost} />} cursor={{ fill: `${C.muted}15` }} />
          {models.map((model, i) => (
            <Bar
              key={model}
              dataKey={model}
              fill={LINE_COLORS[i % LINE_COLORS.length]}
              radius={[3, 3, 0, 0]}
              opacity={selected === null || selected === model ? 1 : 0.15}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <ChartLegend models={models} selected={selected} onSelect={setSelected} totals={totals} fmtValue={fmtCost} />
    </div>
  );
}

// ─── Requests Bar Chart (grouped) ───────────────────────────────────────────
function RequestsBarChart({ records, range, mobile }: { records: ApiCall[]; range: Range; mobile: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const { data, models } = useMemo(() => buildBarData(records, range, "requests", MAX_GROUPED_BINS), [records, range]);
  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    for (const m of models) t[m] = data.reduce((s, r) => s + ((r[m] as number) ?? 0), 0);
    return t;
  }, [data, models]);
  const grandTotal = Object.values(totals).reduce((s, v) => s + v, 0);

  if (data.length === 0 || models.length === 0) {
    return (
      <div style={chartCardStyle}>
        <div style={chartTitleStyle}>Requests by Model</div>
        <EmptyState label="No request data for this period" />
      </div>
    );
  }

  return (
    <div style={chartCardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
        <div>
          <div style={chartTitleStyle}>Requests by Model</div>
          <div style={{ color: C.muted, fontSize: "0.78rem" }}>Total: {fmtNum(grandTotal)}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={mobile ? 220 : 260}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap="20%" barGap={1}>
          <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => fmtNum(v)} width={40} scale="log" domain={['auto', 'auto']} allowDataOverflow />
          <Tooltip content={<BarTooltip fmtValue={fmtNum} />} cursor={{ fill: `${C.muted}15` }} />
          {models.map((model, i) => (
            <Bar
              key={model}
              dataKey={model}
              fill={LINE_COLORS[i % LINE_COLORS.length]}
              radius={[3, 3, 0, 0]}
              opacity={selected === null || selected === model ? 1 : 0.15}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <ChartLegend models={models} selected={selected} onSelect={setSelected} totals={totals} fmtValue={fmtNum} />
    </div>
  );
}

// ─── Tokens 100% Stacked Bar Chart ──────────────────────────────────────────
function TokensStackedChart({ records, range, mobile }: { records: ApiCall[]; range: Range; mobile: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const { data: rawData, models } = useMemo(() => buildBarData(records, range, "tokens", MAX_STACKED_BINS), [records, range]);
  const normData = useMemo(() => normalizeToPercent(rawData, models), [rawData, models]);

  // Per-model total tokens for legend
  const totals = useMemo(() => {
    const t: Record<string, number> = {};
    for (const m of models) t[m] = rawData.reduce((s, r) => s + ((r[m] as number) ?? 0), 0);
    return t;
  }, [rawData, models]);

  if (rawData.length === 0 || models.length === 0) {
    return (
      <div style={chartCardStyle}>
        <div style={chartTitleStyle}>Token Usage Share</div>
        <EmptyState label="No token data for this period" />
      </div>
    );
  }

  return (
    <div style={chartCardStyle}>
      <div style={{ marginBottom: "0.5rem" }}>
        <div style={chartTitleStyle}>Token Usage Share</div>
        <div style={{ color: C.muted, fontSize: "0.78rem" }}>Relative proportion per time bucket (100% normalized)</div>
      </div>
      <ResponsiveContainer width="100%" height={mobile ? 240 : 280}>
        <BarChart data={normData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap="12%">
          <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis domain={[0, 100]} tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} width={40} />
          <Tooltip
            content={(props: any) => (
              <BarTooltip {...props} fmtValue={fmtNum} showPercent rawData={normData.find(r => r.date === props?.label)} />
            )}
            cursor={{ fill: `${C.muted}15` }}
          />
          {models.map((model, i) => (
            <Bar
              key={model}
              dataKey={model}
              stackId="tokens"
              fill={LINE_COLORS[i % LINE_COLORS.length]}
              opacity={selected === null || selected === model ? 1 : 0.15}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <ChartLegend models={models} selected={selected} onSelect={setSelected} totals={totals} fmtValue={fmtNum} />
    </div>
  );
}

const chartCardStyle: React.CSSProperties = {
  background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1.25rem 1.5rem",
};
const chartTitleStyle: React.CSSProperties = { fontWeight: 600, fontSize: "0.95rem" };

// ─── Linear regression helpers ───────────────────────────────────────────────
function linReg(xs: number[], ys: number[]): { slope: number; intercept: number } {
  const n = xs.length;
  const mx = xs.reduce((s, x) => s + x, 0) / n;
  const my = ys.reduce((s, y) => s + y, 0) / n;
  const num = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0);
  const den = xs.reduce((s, x) => s + (x - mx) ** 2, 0);
  const slope = den === 0 ? 0 : num / den;
  return { slope, intercept: my - slope * mx };
}

function buildDailyBuckets(records: ApiCall[], windowDays: number) {
  const now = new Date();
  const cutoff = new Date(now.getTime() - windowDays * 86_400_000);
  const byDay: Record<string, number> = {};
  for (const r of records) {
    const d = parseTimestamp(r.timestamp);
    if (d < cutoff) continue;
    const key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
    byDay[key] = (byDay[key] ?? 0) + r.cost_usd;
  }
  return Array.from({ length: windowDays + 1 }, (_, i) => {
    const d = new Date(now.getTime() - (windowDays - i) * 86_400_000);
    const key = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
    return { label: `${d.getMonth() + 1}/${d.getDate()}`, dayIndex: i, actual: byDay[key] ?? 0 };
  });
}

// ─── Forecast Tooltip ────────────────────────────────────────────────────────
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ForecastTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const pt = payload[0]?.payload;
  const trend = pt?.histTrend ?? pt?.forecastTrend;
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "0.6rem 0.85rem", boxShadow: "0 4px 20px rgba(0,0,0,0.4)" }}>
      <div style={{ fontSize: "0.75rem", color: C.muted, marginBottom: 6 }}>{label}{pt?.isForecast ? " (forecast)" : ""}</div>
      {pt?.actual !== undefined && (
        <div style={{ fontSize: "0.82rem", marginBottom: 3 }}>
          <span style={{ color: C.muted }}>Actual: </span>
          <span style={{ fontWeight: 600 }}>{fmtCost(pt.actual)}</span>
        </div>
      )}
      {trend !== undefined && (
        <div style={{ fontSize: "0.82rem", marginBottom: pt?.isForecast ? 3 : 0 }}>
          <span style={{ color: C.muted }}>{pt?.isForecast ? "Forecast: " : "Trend: "}</span>
          <span style={{ fontWeight: 600, color: C.accentLight }}>{fmtCost(trend)}</span>
        </div>
      )}
      {pt?.isForecast && pt?.lower !== undefined && (
        <div style={{ fontSize: "0.78rem", color: C.muted }}>
          95% CI: {fmtCost(pt.lower)} – {fmtCost(pt.lower + pt.bandWidth)}
        </div>
      )}
    </div>
  );
}

// ─── Cost Forecast Chart ──────────────────────────────────────────────────────
function CostForecastChart({ records, mobile }: { records: ApiCall[]; mobile: boolean }) {
  const HISTORY_DAYS = 14;
  const FORECAST_DAYS = 7;
  const Z = 1.96; // 95% CI

  const { chartData, forecastTotal } = useMemo(() => {
    const historical = buildDailyBuckets(records, HISTORY_DAYS);
    const xs = historical.map(d => d.dayIndex);
    const ys = historical.map(d => d.actual);
    const { slope, intercept } = linReg(xs, ys);

    // Standard error for confidence band
    const n = xs.length;
    const xbar = xs.reduce((s, x) => s + x, 0) / n;
    const sxx = xs.reduce((s, x) => s + (x - xbar) ** 2, 0);
    const sse = ys.reduce((s, y, i) => s + (y - (slope * xs[i] + intercept)) ** 2, 0);
    const se = n > 2 ? Math.sqrt(sse / (n - 2)) : 0;

    const predict = (xi: number) => {
      const y = Math.max(0, slope * xi + intercept);
      const margin = Z * se * Math.sqrt(1 / n + (xi - xbar) ** 2 / (sxx || 1));
      return { y, lower: Math.max(0, y - margin), upper: Math.max(0, y + margin) };
    };

    const data: {
      label: string; actual?: number;
      histTrend?: number; forecastTrend?: number;
      lower?: number; bandWidth?: number; isForecast: boolean;
    }[] = historical.map(d => {
      const { y } = predict(d.dayIndex);
      return { label: d.label, actual: d.actual, histTrend: y, isForecast: false };
    });

    // Boundary point: last historical also starts forecast line
    const lastXi = HISTORY_DAYS;
    const { y: boundaryY } = predict(lastXi);
    data[data.length - 1].forecastTrend = boundaryY;

    let total = 0;
    for (let i = 1; i <= FORECAST_DAYS; i++) {
      const xi = HISTORY_DAYS + i;
      const d = new Date(Date.now() + i * 86_400_000);
      const label = `${d.getMonth() + 1}/${d.getDate()}`;
      const { y, lower, upper } = predict(xi);
      total += y;
      data.push({ label, forecastTrend: y, lower, bandWidth: upper - lower, isForecast: true });
    }

    return { chartData: data, forecastTotal: total };
  }, [records]);

  if (records.length < 3) {
    return (
      <div style={chartCardStyle}>
        <div style={chartTitleStyle}>7-Day Cost Forecast</div>
        <EmptyState label="Need at least 3 records to generate a forecast" />
      </div>
    );
  }

  return (
    <div style={chartCardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
        <div>
          <div style={chartTitleStyle}>7-Day Cost Forecast</div>
          <div style={{ color: C.muted, fontSize: "0.78rem" }}>Linear trend on last 14 days · 95% confidence band</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: "0.75rem", color: C.muted }}>Projected 7-day spend</div>
          <div style={{ fontWeight: 700, fontSize: "1.1rem", color: C.accentLight }}>{fmtCost(forecastTotal)}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={mobile ? 220 : 260}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
          <XAxis dataKey="label" tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fill: C.muted, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={fmtCost} width={54} />
          <Tooltip content={<ForecastTooltip />} cursor={{ fill: `${C.muted}10` }} />
          {/* Confidence band using stacked area trick */}
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} legendType="none" />
          <Area dataKey="bandWidth" stackId="band" stroke="none" fill={C.accent} fillOpacity={0.13} isAnimationActive={false} legendType="none" />
          {/* Actual daily cost bars */}
          <Bar dataKey="actual" fill={C.accent} fillOpacity={0.65} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          {/* Solid trend line over historical */}
          <Line dataKey="histTrend" stroke={C.accentLight} strokeWidth={2} dot={false} isAnimationActive={false} legendType="none" connectNulls />
          {/* Dashed forecast line */}
          <Line dataKey="forecastTrend" stroke={C.accentLight} strokeWidth={2} strokeDasharray="5 3" dot={false} isAnimationActive={false} legendType="none" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: "1rem", marginTop: "0.5rem", fontSize: "0.75rem", color: C.muted, flexWrap: "wrap" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 10, height: 10, background: C.accent, borderRadius: 2, opacity: 0.65, flexShrink: 0 }} />
          Actual daily cost
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 16, height: 2, background: C.accentLight, flexShrink: 0 }} />
          Trend · · · Forecast
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ width: 14, height: 8, background: C.accent, borderRadius: 2, opacity: 0.15, flexShrink: 0 }} />
          95% confidence
        </span>
      </div>
    </div>
  );
}

// ─── Filter Bar ──────────────────────────────────────────────────────────────
function FilterBar({ filters, onChange, options, hasActive, mobile }: {
  filters: { provider: string; appTag: string; keyHint: string };
  onChange: (f: { provider: string; appTag: string; keyHint: string }) => void;
  options: { providers: string[]; appTags: string[]; keyHints: string[] };
  hasActive: boolean;
  mobile: boolean;
}) {
  const selectStyle: React.CSSProperties = {
    background: C.bg, color: C.text, border: `1px solid ${C.border}`,
    borderRadius: 6, padding: "0.35rem 0.5rem", fontSize: "0.78rem", cursor: "pointer",
    minWidth: 0, maxWidth: mobile ? 120 : 160,
  };
  const labelStyle: React.CSSProperties = {
    fontSize: "0.7rem", color: C.muted, textTransform: "uppercase", letterSpacing: "0.04em",
  };

  return (
    <div style={{
      padding: mobile ? "0.5rem 1rem" : "0.5rem 2rem",
      borderBottom: `1px solid ${C.border}`,
      background: C.surface,
      display: "flex", alignItems: "center", gap: mobile ? "0.5rem" : "1rem",
      flexWrap: "wrap", flexShrink: 0,
    }}>
      <span style={{ ...labelStyle, flexShrink: 0 }}>Filters</span>

      <FilterSelect
        label="Provider"
        value={filters.provider}
        options={options.providers}
        onChange={v => onChange({ ...filters, provider: v })}
        style={selectStyle}
      />
      <FilterSelect
        label="App Tag"
        value={filters.appTag}
        options={options.appTags}
        onChange={v => onChange({ ...filters, appTag: v })}
        style={selectStyle}
      />
      <FilterSelect
        label="API Key"
        value={filters.keyHint}
        options={options.keyHints}
        formatOption={v => `…${v}`}
        onChange={v => onChange({ ...filters, keyHint: v })}
        style={selectStyle}
      />

      {hasActive && (
        <button
          onClick={() => onChange({ provider: "all", appTag: "all", keyHint: "all" })}
          style={{
            background: "transparent", border: `1px solid ${C.border}`, borderRadius: 6,
            color: C.muted, fontSize: "0.75rem", padding: "0.3rem 0.6rem", cursor: "pointer",
            whiteSpace: "nowrap",
          }}
        >
          Clear all
        </button>
      )}
    </div>
  );
}

function FilterSelect({ label, value, options, onChange, style, formatOption }: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
  style: React.CSSProperties;
  formatOption?: (v: string) => string;
}) {
  const isActive = value !== "all";
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      aria-label={`Filter by ${label}`}
      style={{
        ...style,
        ...(isActive ? { borderColor: C.accent, color: C.accentLight } : {}),
      }}
    >
      <option value="all">All {label.toLowerCase()}s</option>
      {options.map(o => (
        <option key={o} value={o}>{formatOption ? formatOption(o) : o}</option>
      ))}
    </select>
  );
}

// ─── Overview ─────────────────────────────────────────────────────────────────
function OverviewPage({ summary, records, dashSummary, loading, gran, range, mobile }: {
  summary: ApiCallSummary[];
  records: ApiCall[];
  dashSummary: { total_tokens_in: number; total_tokens_out: number; total_cost_usd: number; request_count: number; avg_latency_ms: number } | undefined;
  loading: boolean;
  gran: Granularity;
  range: Range;
  mobile: boolean;
}) {
  return (
    <div>
      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: mobile ? "repeat(2, 1fr)" : "repeat(4, 1fr)", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <KpiCard label="Total Spend" value={loading ? "—" : fmtCost(dashSummary?.total_cost_usd ?? 0)} />
        <KpiCard label="Total Tokens" value={loading ? "—" : fmtNum((dashSummary?.total_tokens_in ?? 0) + (dashSummary?.total_tokens_out ?? 0))} />
        <KpiCard label="API Calls" value={loading ? "—" : fmtNum(dashSummary?.request_count ?? 0)} />
        <KpiCard label="Avg Latency" value={loading ? "—" : `${(dashSummary?.avg_latency_ms ?? 0).toFixed(0)}ms`} />
      </div>

      {/* Cost + Requests side by side on desktop */}
      <div style={{ display: "grid", gridTemplateColumns: mobile ? "1fr" : "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <CostBarChart records={records} range={range} mobile={mobile} />
        <RequestsBarChart records={records} range={range} mobile={mobile} />
      </div>

      {/* Token share — full width */}
      <div style={{ marginBottom: "1rem" }}>
        <TokensStackedChart records={records} range={range} mobile={mobile} />
      </div>

      {/* Cost forecast — full width */}
      <div style={{ marginBottom: "1.25rem" }}>
        <CostForecastChart records={records} mobile={mobile} />
      </div>

      <Card title="Recent requests" subtitle={`${records.length} total`}>
        <RequestsTable records={records.slice(0, 10)} />
      </Card>
    </div>
  );
}

// ─── Usage ────────────────────────────────────────────────────────────────────
function UsagePage({ summary, records, loading, mobile }: { summary: ApiCallSummary[]; records: ApiCall[]; loading: boolean; mobile: boolean }) {
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: mobile ? "1fr" : "repeat(3, 1fr)", gap: "1rem", marginBottom: "1.5rem" }}>
        {summary.map(s => (
          <div key={`${s.provider}-${s.model}`} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
            {/* Header */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: "0.9rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.model}</div>
              </div>
              <ProviderBadge provider={s.provider} small />
            </div>
            {/* Metrics 2x2 grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem 1rem" }}>
              <div style={{ padding: "0.4rem 0", borderTop: `1px solid ${C.border}` }}>
                <div style={{ color: C.muted, fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 2 }}>Requests</div>
                <div style={{ fontWeight: 600, fontSize: "1rem" }}>{fmtNum(s.request_count)}</div>
              </div>
              <div style={{ padding: "0.4rem 0", borderTop: `1px solid ${C.border}` }}>
                <div style={{ color: C.muted, fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 2 }}>Cost</div>
                <div style={{ fontWeight: 600, fontSize: "1rem", color: C.accentLight }}>{fmtCost(s.total_cost_usd)}</div>
              </div>
              <div style={{ padding: "0.4rem 0", borderTop: `1px solid ${C.border}` }}>
                <div style={{ color: C.muted, fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 2 }}>In tokens</div>
                <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{fmtNum(s.total_tokens_in)}</div>
              </div>
              <div style={{ padding: "0.4rem 0", borderTop: `1px solid ${C.border}` }}>
                <div style={{ color: C.muted, fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 2 }}>Out tokens</div>
                <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{fmtNum(s.total_tokens_out)}</div>
              </div>
            </div>
          </div>
        ))}
        {summary.length === 0 && !loading && (
          <div style={{ gridColumn: "1/-1" }}>
            <EmptyState label="No usage recorded yet. Log your first API call to see stats here." />
          </div>
        )}
      </div>

      <Card title="All requests" subtitle={`${records.length} records`}>
        <RequestsTable records={records} />
      </Card>
    </div>
  );
}

// ─── API Keys ─────────────────────────────────────────────────────────────────

// ─── Settings ─────────────────────────────────────────────────────────────────
function SettingsPage({ quota, user, mobile }: { quota: { limit: number; used: number; remaining: number; reset_at: number; window_ms: number } | undefined; user?: UserOut | null; mobile?: boolean }) {
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
  const [confirmRegen, setConfirmRegen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Auto-load existing token on mount
  useEffect(() => { fetchSdkToken().then(r => setSdkToken(r.sdk_token)).catch(() => {}); }, []);

  async function handleRegenerate() {
    setConfirmRegen(false);
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
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem", maxWidth: mobile ? "100%" : 560 }}>
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
            {confirmRegen ? (
              <>
                <span style={{ fontSize: "0.82rem", color: C.red }}>Old token will stop working.</span>
                <button onClick={handleRegenerate} disabled={sdkLoading} style={{ ...btnStyle(C.red) }}>Confirm</button>
                <button onClick={() => setConfirmRegen(false)} style={{ ...btnStyle(C.border) }}>Cancel</button>
              </>
            ) : (
              <button onClick={() => setConfirmRegen(true)} disabled={sdkLoading} style={{ ...btnStyle(C.muted) }}>
                {sdkLoading ? "Rotating…" : "Regenerate"}
              </button>
            )}
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

      <Card title="Rate limits" subtitle="Set monthly token budgets per user — coming soon">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem", opacity: 0.5, pointerEvents: "none" }}>
          <LabeledInput label="Monthly token limit" defaultValue="5000000" />
          <LabeledInput label="Daily token limit" defaultValue="500000" />
          <LabeledInput label="Alert threshold (%)" defaultValue="80" />
          <button style={{ ...btnStyle(C.accent), alignSelf: "flex-start", marginTop: "0.25rem" }}>Save limits</button>
        </div>
      </Card>

      <Card title="SMS Alerts" subtitle="Get texted when you hit 80% or 100% of your daily token quota">
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "0.75rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
            <label htmlFor="phone-input" style={{ fontSize: "0.82rem", color: C.subtle }}>Phone number (E.164 format)</label>
            <input
              id="phone-input"
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
          {confirmDelete ? (
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.85rem", color: C.red }}>This will permanently delete all your usage data.</span>
              <button onClick={() => setConfirmDelete(false)} style={{ ...btnStyle(C.border) }}>Cancel</button>
              <button style={{ ...btnStyle(C.red) }}>Delete everything</button>
            </div>
          ) : (
            <button onClick={() => setConfirmDelete(true)} style={btnStyle(C.red)}>Delete all usage records</button>
          )}
        </div>
      </Card>
    </div>
  );
}
const FLAG_COLORS: Record<string, string> = {
  low: C.green,
  medium: C.yellow,
  high: C.red,
};

// ─── Shared components ────────────────────────────────────────────────────────
const FLAG_ICONS: Record<string, string> = { low: "↓", medium: "→", high: "↑" };

function RequestsTable({ records }: { records: ApiCall[] }) {
  if (records.length === 0) return <EmptyState label="No requests yet." />;
  return (
    <div style={{ overflowX: "auto", marginTop: "0.5rem" }} role="region" aria-label="Requests table" tabIndex={0}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
        <caption style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}>API request history</caption>
        <thead>
          <tr>
            {["Time", "Provider", "Model", "App Tag", "Key", "In", "Out", "Latency", "Cost", "Level"].map(h => (
              <th key={h} scope="col" style={{ textAlign: "left", padding: "0.5rem 0.75rem", color: C.muted, fontSize: "0.8rem", fontWeight: 500, borderBottom: `1px solid ${C.border}`, whiteSpace: "nowrap" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map(r => (
            <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
              <td style={tdStyle}>{new Date(r.timestamp).toLocaleString(undefined, { timeZoneName: 'short' })}</td>
              <td style={tdStyle}><ProviderBadge provider={r.provider} small /></td>
              <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: "0.8rem" }}>{r.model}</td>
              <td style={{ ...tdStyle, color: C.muted }}>{r.app_tag ?? "—"}</td>
              <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: "0.78rem", color: C.muted }}>{r.key_hint ? `…${r.key_hint}` : "—"}</td>
              <td style={tdStyle}>{r.tokens_in.toLocaleString()}</td>
              <td style={tdStyle}>{r.tokens_out.toLocaleString()}</td>
              <td style={{ ...tdStyle, color: C.subtle }}>{r.latency_ms}ms</td>
              <td style={{ ...tdStyle, color: C.accentLight, fontWeight: 600 }}>{fmtCost(r.cost_usd)}</td>
              <td style={tdStyle}>
                {r.cost_flag ? (
                  <Pill color={FLAG_COLORS[r.cost_flag]}>
                    {FLAG_ICONS[r.cost_flag]} {r.cost_flag.charAt(0).toUpperCase() + r.cost_flag.slice(1)}
                  </Pill>
                ) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  const isLoading = value === "—";
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: "1rem 1.25rem" }}>
      <div style={{ color: C.muted, fontSize: "0.75rem", marginBottom: "0.35rem" }}>{label}</div>
      {isLoading ? (
        <div style={{ height: "1.75rem", width: "60%", background: C.border, borderRadius: 6, animation: "pulse 1.5s ease-in-out infinite" }} />
      ) : (
        <div style={{ fontSize: "clamp(1.1rem, 4vw, 1.75rem)", fontWeight: 700, letterSpacing: "-0.03em" }}>{value}</div>
      )}
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
      <div style={{ marginBottom: "0.5rem", display: "flex", justifyContent: "center" }}><IconEmpty /></div>
      {label}
    </div>
  );
}

let labeledIdCounter = 0;
function LabeledInput({ label, defaultValue, placeholder }: { label: string; defaultValue?: string; placeholder?: string }) {
  const [id] = useState(() => `labeled-${++labeledIdCounter}`);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <label htmlFor={id} style={{ fontSize: "0.82rem", color: C.subtle }}>{label}</label>
      <input
        id={id}
        defaultValue={defaultValue}
        placeholder={placeholder}
        style={{ background: C.bg, color: C.text, border: `1px solid ${C.border}`, borderRadius: 8, padding: "0.5rem 0.75rem", fontSize: "0.9rem" }}
      />
    </div>
  );
}

function btnStyle(color: string): React.CSSProperties {
  return { background: color, color: C.onAccent, border: "none", borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 };
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
