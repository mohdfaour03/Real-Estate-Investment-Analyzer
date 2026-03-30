import { useTheme } from "../context/ThemeContext";

/**
 * Header — sticky top bar with logo, title, theme toggle, and New Chat button.
 */
export default function Header({ onNewChat, activeAgent, onToggleAgent }) {
  const { colors, isDark, toggleTheme } = useTheme();

  return (
    <header style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "14px 24px", borderBottom: `1px solid ${colors.border}`,
      background: `linear-gradient(180deg, ${colors.bgSecondary} 0%, ${colors.bg} 100%)`,
      backdropFilter: "blur(12px)", position: "sticky", top: 0, zIndex: 10,
    }}>
      {/* Left: logo + title */}
      <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
        <div style={{
          width: "36px", height: "36px", borderRadius: "10px",
          background: colors.gradient, display: "flex", alignItems: "center",
          justifyContent: "center", fontSize: "15px", fontWeight: 800,
          color: "white", animation: "pulseGlow 3s infinite ease-in-out",
        }}>RE</div>
        <div>
          <h1 style={{
            margin: 0, fontSize: "16px", fontWeight: 650, color: colors.text,
            letterSpacing: "-0.3px",
          }}>Real Estate Investment Analyzer</h1>
          <p style={{
            margin: "2px 0 0", fontSize: "11px", color: colors.textFaint,
            letterSpacing: "0.2px",
          }}>
            UAE Rental Market · Multi-Agent System · inmind.academy
          </p>
        </div>
      </div>

      {/* Right: agent toggle + theme toggle + New Chat button */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {/* Agent toggle */}
        {onToggleAgent && (
          <button
            onClick={onToggleAgent}
            title={activeAgent === "A" ? "Switch to Agent B (direct)" : "Switch to Agent A (full system)"}
            style={{
              display: "flex", alignItems: "center", gap: "6px",
              padding: "8px 14px", borderRadius: "10px",
              border: `1px solid ${colors.border}`,
              backgroundColor: colors.surface,
              color: colors.textMuted,
              fontSize: "12px", fontWeight: 600,
              cursor: "pointer", transition: "all 200ms ease",
              fontFamily: "inherit",
            }}
          >
            {activeAgent === "A" ? "Agent A" : "Agent B"}
          </button>
        )}

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          title={isDark ? "Switch to light mode" : "Switch to dark mode"}
          aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            width: "36px", height: "36px", borderRadius: "10px",
            border: `1px solid ${colors.border}`,
            backgroundColor: colors.surface,
            color: colors.textMuted, fontSize: "16px",
            cursor: "pointer", transition: "all 200ms ease",
            fontFamily: "inherit",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = colors.accent;
            e.currentTarget.style.color = colors.text;
            e.currentTarget.style.backgroundColor = colors.surfaceHover;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = colors.border;
            e.currentTarget.style.color = colors.textMuted;
            e.currentTarget.style.backgroundColor = colors.surface;
          }}
        >
          {isDark ? "☀️" : "🌙"}
        </button>

        {/* New Chat button */}
        <button
          onClick={onNewChat}
          aria-label="Start new chat"
          style={{
            display: "flex", alignItems: "center", gap: "6px",
            padding: "8px 16px", borderRadius: "10px",
            border: `1px solid ${colors.border}`,
            backgroundColor: colors.surface,
            color: colors.textMuted, fontSize: "12px", fontWeight: 500,
            cursor: "pointer", transition: "all 200ms ease",
            fontFamily: "inherit",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = colors.accent;
            e.currentTarget.style.color = colors.text;
            e.currentTarget.style.backgroundColor = colors.surfaceHover;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = colors.border;
            e.currentTarget.style.color = colors.textMuted;
            e.currentTarget.style.backgroundColor = colors.surface;
          }}
        >
          <span style={{ fontSize: "16px", lineHeight: 1 }}>+</span>
          New Chat
        </button>
      </div>
    </header>
  );
}
