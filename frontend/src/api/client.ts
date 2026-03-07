const BASE = "";

export interface UsageRecord {
  id: number;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  project: string | null;
  created_at: string;
}

export interface UsageSummary {
  provider: string;
  model: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  request_count: number;
}

export interface UsageRecordCreate {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  project?: string;
}

export async function fetchRecords(limit = 100): Promise<UsageRecord[]> {
  const res = await fetch(`${BASE}/usage/?limit=${limit}`);
  return res.json();
}

export async function fetchSummary(): Promise<UsageSummary[]> {
  const res = await fetch(`${BASE}/usage/summary`);
  return res.json();
}

export async function logUsage(record: UsageRecordCreate): Promise<UsageRecord> {
  const res = await fetch(`${BASE}/usage/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(record),
  });
  return res.json();
}

export async function deleteRecord(id: number): Promise<void> {
  await fetch(`${BASE}/usage/${id}`, { method: "DELETE" });
}
