const BASE = "";

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh_token = localStorage.getItem("refresh_token");
  if (!refresh_token) return false;
  try {
    const res = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    return true;
  } catch {
    return false;
  }
}

async function get<T>(path: string): Promise<T> {
  console.log(`[API] GET ${BASE + path}`);
  let res = await fetch(BASE + path, { headers: authHeaders() });
  console.log(`[API] GET ${BASE + path} → ${res.status} ${res.statusText}`);
  if (res.status === 401) {
    const ok = await refreshAccessToken();
    if (ok) res = await fetch(BASE + path, { headers: authHeaders() });
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const url = BASE + path;
  console.log(`[API] POST ${url}`, body);
  let res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  console.log(`[API] POST ${url} → ${res.status} ${res.statusText}`);
  if (res.status === 401 && path !== "/api/v1/auth/refresh") {
    const ok = await refreshAccessToken();
    if (ok) {
      res = await fetch(BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

// ── Auth types & endpoints ────────────────────────────────────────────────────

export interface UserOut {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  user?: UserOut;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return post("/api/v1/auth/login", { email, password });
}

export function register(email: string, password: string, full_name?: string): Promise<AuthResponse> {
  return post("/api/v1/auth/register", { email, password, full_name });
}

export async function logout(): Promise<void> {
  const refresh_token = localStorage.getItem("refresh_token");
  if (refresh_token) {
    await post("/api/v1/auth/logout", { refresh_token }).catch(() => {});
  }
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
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

export function fetchSdkToken(): Promise<{ sdk_token: string }> {
  return get("/api/v1/auth/sdk-token");
}

export function regenerateSdkToken(): Promise<{ sdk_token: string }> {
  return get("/api/v1/auth/sdk-token?regenerate=true");
}
