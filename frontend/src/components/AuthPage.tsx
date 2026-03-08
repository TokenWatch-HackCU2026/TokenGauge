import { useState } from "react";
import { login, register, AuthResponse } from "../api/client";

const C = {
  bg: "#0a0e1a",
  surface: "#111827",
  border: "#1e2d40",
  accent: "#6366f1",
  accentLight: "#818cf8",
  red: "#ef4444",
  text: "#f1f5f9",
  muted: "#64748b",
  subtle: "#94a3b8",
} as const;

interface Props {
  onAuth: (tokens: AuthResponse) => void;
}

export default function AuthPage({ onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSlow(false);
    setLoading(true);
    const slowTimer = setTimeout(() => setSlow(true), 5000);
    try {
      const res =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, fullName || undefined);
      onAuth(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      clearTimeout(slowTimer);
      setLoading(false);
      setSlow(false);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "'Inter', system-ui, sans-serif",
        color: C.text,
      }}
    >
      <div style={{ width: "100%", maxWidth: 400, padding: "0 1rem" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: C.accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "1.5rem",
              margin: "0 auto 0.75rem",
            }}
          >
            ⬡
          </div>
          <div style={{ fontWeight: 700, fontSize: "1.4rem", letterSpacing: "-0.03em" }}>
            TokenWatch
          </div>
          <div style={{ color: C.muted, fontSize: "0.875rem", marginTop: "0.25rem" }}>
            {mode === "login" ? "Sign in to your account" : "Create your account"}
          </div>
        </div>

        {/* Card */}
        <div
          style={{
            background: C.surface,
            border: `1px solid ${C.border}`,
            borderRadius: 16,
            padding: "2rem",
          }}
        >
          {/* Tab switcher */}
          <div
            style={{
              display: "flex",
              background: C.bg,
              borderRadius: 10,
              padding: 4,
              marginBottom: "1.5rem",
            }}
          >
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(null); }}
                style={{
                  flex: 1,
                  padding: "0.5rem",
                  border: "none",
                  borderRadius: 8,
                  cursor: "pointer",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  background: mode === m ? C.accent : "transparent",
                  color: mode === m ? "#fff" : C.muted,
                  transition: "all 0.15s",
                }}
              >
                {m === "login" ? "Sign in" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {mode === "register" && (
              <Field
                label="Full name"
                type="text"
                placeholder="Jane Smith"
                value={fullName}
                onChange={setFullName}
              />
            )}
            <Field
              label="Email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={setEmail}
              required
            />
            <Field
              label="Password"
              type="password"
              placeholder={mode === "register" ? "Min 8 characters" : "••••••••"}
              value={password}
              onChange={setPassword}
              required
            />

            {error && (
              <div
                style={{
                  background: `${C.red}18`,
                  border: `1px solid ${C.red}44`,
                  borderRadius: 8,
                  padding: "0.6rem 0.85rem",
                  fontSize: "0.85rem",
                  color: C.red,
                }}
              >
                {error}
              </div>
            )}

            {slow && (
              <div
                style={{
                  background: `#6366f118`,
                  border: `1px solid #6366f144`,
                  borderRadius: 8,
                  padding: "0.6rem 0.85rem",
                  fontSize: "0.82rem",
                  color: C.subtle,
                  textAlign: "center",
                }}
              >
                Server is waking up — this can take up to 30 seconds on first visit.
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                background: loading ? C.muted : C.accent,
                color: "#fff",
                border: "none",
                borderRadius: 10,
                padding: "0.7rem",
                fontSize: "0.95rem",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                marginTop: "0.25rem",
                transition: "background 0.15s",
              }}
            >
              {loading
                ? "Please wait…"
                : mode === "login"
                ? "Sign in"
                : "Create account"}
            </button>
          </form>
        </div>

        <p style={{ textAlign: "center", color: C.muted, fontSize: "0.8rem", marginTop: "1.5rem" }}>
          {mode === "login" ? "Don't have an account? " : "Already have an account? "}
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
            style={{
              background: "none",
              border: "none",
              color: C.accentLight,
              cursor: "pointer",
              fontSize: "0.8rem",
              fontWeight: 600,
              padding: 0,
            }}
          >
            {mode === "login" ? "Register" : "Sign in"}
          </button>
        </p>
      </div>
    </div>
  );
}

function Field({
  label,
  type,
  placeholder,
  value,
  onChange,
  required,
}: {
  label: string;
  type: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
      <label style={{ fontSize: "0.82rem", color: C.subtle, fontWeight: 500 }}>{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        style={{
          background: C.bg,
          color: C.text,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "0.6rem 0.75rem",
          fontSize: "0.9rem",
          outline: "none",
        }}
      />
    </div>
  );
}
