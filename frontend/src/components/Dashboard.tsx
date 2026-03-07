import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { fetchSummary, fetchRecords, UsageSummary, UsageRecord } from "../api/client";

export default function Dashboard() {
  const [summary, setSummary] = useState<UsageSummary[]>([]);
  const [records, setRecords] = useState<UsageRecord[]>([]);

  const load = async () => {
    const [s, r] = await Promise.all([fetchSummary(), fetchRecords()]);
    setSummary(s);
    setRecords(r);
  };

  useEffect(() => {
    load();
  }, []);

  const totalCost = summary.reduce((acc, s) => acc + s.total_cost_usd, 0);
  const totalTokens = summary.reduce(
    (acc, s) => acc + s.total_input_tokens + s.total_output_tokens,
    0
  );

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>TokenWatch</h1>

      <div style={{ display: "flex", gap: "2rem", marginBottom: "2rem" }}>
        <StatCard label="Total Cost" value={`$${totalCost.toFixed(4)}`} />
        <StatCard label="Total Tokens" value={totalTokens.toLocaleString()} />
        <StatCard label="Requests" value={records.length.toString()} />
      </div>

      <h2>Cost by Model</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={summary}>
          <XAxis dataKey="model" />
          <YAxis />
          <Tooltip formatter={(v: number) => `$${v.toFixed(4)}`} />
          <Bar dataKey="total_cost_usd" fill="#6366f1" name="Cost (USD)" />
        </BarChart>
      </ResponsiveContainer>

      <h2 style={{ marginTop: "2rem" }}>Recent Requests</h2>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {["Time", "Provider", "Model", "In", "Out", "Cost"].map((h) => (
              <th key={h} style={{ textAlign: "left", borderBottom: "1px solid #ccc", padding: "0.5rem" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <td style={td}>{new Date(r.created_at).toLocaleString()}</td>
              <td style={td}>{r.provider}</td>
              <td style={td}>{r.model}</td>
              <td style={td}>{r.input_tokens.toLocaleString()}</td>
              <td style={td}>{r.output_tokens.toLocaleString()}</td>
              <td style={td}>${r.cost_usd.toFixed(6)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const td: React.CSSProperties = { padding: "0.5rem", borderBottom: "1px solid #eee" };

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "#f4f4f8", borderRadius: "8px", padding: "1rem 2rem", minWidth: "150px" }}>
      <div style={{ fontSize: "0.85rem", color: "#666" }}>{label}</div>
      <div style={{ fontSize: "1.75rem", fontWeight: "bold" }}>{value}</div>
    </div>
  );
}
