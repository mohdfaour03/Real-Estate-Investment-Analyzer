import { useTheme } from "../context/ThemeContext";

const SUGGESTIONS = [
  "Compare Downtown vs Business Bay",
  "Best areas for 8%+ yield",
];

export default function SuggestionChips({ onSelect, visible }) {
  const { colors } = useTheme();

  if (!visible) return null;

  return (
    <div style={{
      padding: "0 24px 10px", display: "flex", gap: "8px",
      flexWrap: "wrap", justifyContent: "center",
    }}>
      {SUGGESTIONS.map((text, i) => (
        <button
          key={i}
          onClick={() => onSelect(text)}
          aria-label={`Ask: ${text}`}
          style={{
            padding: "8px 16px", borderRadius: "20px",
            border: `1px solid ${colors.border}`, backgroundColor: colors.surface,
            color: colors.textMuted, fontSize: "12px", fontWeight: 500,
            cursor: "pointer", transition: "all 200ms ease",
            letterSpacing: "0.1px",
          }}
          onMouseEnter={e => {
            e.target.style.borderColor = colors.accent;
            e.target.style.color = colors.text;
            e.target.style.backgroundColor = colors.surfaceHover;
            e.target.style.transform = "translateY(-1px)";
          }}
          onMouseLeave={e => {
            e.target.style.borderColor = colors.border;
            e.target.style.color = colors.textMuted;
            e.target.style.backgroundColor = colors.surface;
            e.target.style.transform = "translateY(0)";
          }}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
