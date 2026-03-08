// ─── Shared Theme — Blue / Yellow / Red gauge palette ────────────────────────
export const C = {
  bg: "#0a0e1a",
  surface: "#111827",
  border: "#1e2d40",

  // Primary — golden orange (matches favicon gauge)
  accent: "#fcb731",
  accentLight: "#fdc94f",
  accentDim: "rgba(252,183,49,0.15)",

  // Semantic
  green: "#10b981",
  red: "#ef4444",
  yellow: "#fcb731",

  // Text
  text: "#f1f5f9",
  muted: "#7c8db0",
  subtle: "#94a3b8",
  onAccent: "#ffffff",
} as const;

export const PROVIDER_COLORS: Record<string, string> = {
  openai: "#10a37f",
  anthropic: "#d97706",
  google: "#4285f4",
  mistral: "#7c3aed",
};

export const PIE_COLORS = ["#38a1f3", "#8b5cf6", "#06b6d4", "#10b981", "#fcb731", "#ef4444"];
export const LINE_COLORS = ["#38a1f3", "#10b981", "#fcb731", "#ef4444", "#06b6d4", "#8b5cf6", "#ec4899", "#84cc16"];

// Gauge SVG logo used on auth page and sidebar
export function GaugeLogo({ size = 48 }: { size?: number }) {
  const r = size / 2;
  const strokeW = size * 0.1;
  const arcR = r - strokeW;
  const cx = r;
  const cy = r;

  // Arc helper (SVG arc from startAngle to endAngle in degrees, 0=top)
  function arc(startDeg: number, endDeg: number) {
    const toRad = (d: number) => ((d - 90) * Math.PI) / 180;
    const x1 = cx + arcR * Math.cos(toRad(startDeg));
    const y1 = cy + arcR * Math.sin(toRad(startDeg));
    const x2 = cx + arcR * Math.cos(toRad(endDeg));
    const y2 = cy + arcR * Math.sin(toRad(endDeg));
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${arcR} ${arcR} 0 ${large} 1 ${x2} ${y2}`;
  }

  // Needle pointing to ~40% (around the yellow zone)
  const needleAngle = ((225 + 270 * 0.4) - 90) * Math.PI / 180;
  const needleLen = arcR * 0.7;
  const nx = cx + needleLen * Math.cos(needleAngle);
  const ny = cy + needleLen * Math.sin(needleAngle);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none">
      {/* Blue arc (low zone: 225° to 315°) */}
      <path d={arc(225, 315)} stroke="#38a1f3" strokeWidth={strokeW} strokeLinecap="round" />
      {/* Orange/amber arc (mid zone: 315° to 405°) */}
      <path d={arc(315, 405)} stroke="#fcb731" strokeWidth={strokeW} strokeLinecap="round" />
      {/* Red arc (high zone: 405° to 495° = 135°) */}
      <path d={arc(405, 495)} stroke="#ef4444" strokeWidth={strokeW} strokeLinecap="round" />
      {/* Needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#f1f5f9" strokeWidth={strokeW * 0.45} strokeLinecap="round" />
      {/* Center dot */}
      <circle cx={cx} cy={cy} r={strokeW * 0.6} fill="#f1f5f9" />
    </svg>
  );
}
