const BASE = "";

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(BASE + path, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ApiCall {
  id: string;
  user_id: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
  app_tag: string | null;
  timestamp: string;
}

export interface ApiCallSummary {
  provider: string;
  model: string;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  request_count: number;
}

export interface DashboardSummary {
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: number;
  request_count: number;
  avg_latency_ms: number;
}

export interface TimeseriesPoint {
  date: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  request_count: number;
}

export interface BreakdownRow {
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  request_count: number;
}

export interface QuotaOut {
  limit: number;
  used: number;
  remaining: number;
  reset_at: number;
  window_ms: number;
}

// ── Usage endpoints ───────────────────────────────────────────────────────────

export function fetchRecords(limit = 100): Promise<ApiCall[]> {
  return get(`/usage/?limit=${limit}`);
}

export function fetchSummary(): Promise<ApiCallSummary[]> {
  return get("/usage/summary");
}

export async function logUsage(record: Omit<ApiCall, "id" | "user_id" | "timestamp">): Promise<ApiCall> {
  const res = await fetch(`${BASE}/usage/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(record),
  });
  return res.json();
}

export async function deleteRecord(id: string): Promise<void> {
  await fetch(`${BASE}/usage/${id}`, { method: "DELETE", headers: authHeaders() });
}

// ── Dashboard endpoints ───────────────────────────────────────────────────────

export interface SummaryParams {
  startDate?: string;
  endDate?: string;
  provider?: string;
  model?: string;
  appTag?: string;
}

export interface TimeseriesParams extends SummaryParams {
  groupBy?: "hour" | "day";
}

function toQuery(params: Record<string, string | undefined>): string {
  const q = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v!)}`)
    .join("&");
  return q ? `?${q}` : "";
}

export function fetchDashboardSummary(p: SummaryParams = {}): Promise<DashboardSummary> {
  return get(`/dashboard/summary${toQuery({ start_date: p.startDate, end_date: p.endDate, provider: p.provider, model: p.model, app_tag: p.appTag })}`);
}

export function fetchTimeseries(p: TimeseriesParams = {}): Promise<TimeseriesPoint[]> {
  return get(`/dashboard/timeseries${toQuery({ start_date: p.startDate, end_date: p.endDate, group_by: p.groupBy, provider: p.provider, model: p.model })}`);
}

export function fetchBreakdown(p: SummaryParams = {}): Promise<BreakdownRow[]> {
  return get(`/dashboard/breakdown${toQuery({ start_date: p.startDate, end_date: p.endDate })}`);
}

export function fetchQuota(): Promise<QuotaOut> {
  return get("/dashboard/quota");
}
