import { useTheme } from "../context/ThemeContext";

export default function SourceChips({ sources }) {
  const { colors } = useTheme();

  if (!sources || !sources.length) return null;

  return (
    <div style={{
      display: "flex", gap: "6px", marginTop: "10px", flexWrap: "wrap",
    }}>
      <span style={{ fontSize: "10px", color: colors.textFaint, lineHeight: "22px" }}>Sources:</span>
      {sources.map((src, i) => (
        <span key={i} style={{
          fontSize: "11px", padding: "2px 10px", borderRadius: "10px",
          backgroundColor: colors.sourceBg, color: colors.textMuted,
          border: `1px solid ${colors.border}`, cursor: "pointer",
          transition: "all 150ms ease",
        }}
        onMouseEnter={e => { e.target.style.borderColor = colors.accent; e.target.style.color = colors.text; }}
        onMouseLeave={e => { e.target.style.borderColor = colors.border; e.target.style.color = colors.textMuted; }}
        >{src}</span>
      ))}
    </div>
  );
}
