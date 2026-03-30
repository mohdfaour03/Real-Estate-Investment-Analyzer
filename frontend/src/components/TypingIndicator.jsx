import { useTheme } from "../context/ThemeContext";

export default function TypingIndicator({ status }) {
  const { colors } = useTheme();

  const dot = (delay) => ({
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    backgroundColor: colors.accent,
    animation: `typingDot 1.4s ${delay}s infinite ease-in-out`,
  });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        animation: "fadeIn 300ms ease-out",
      }}
    >
      {/* AI avatar */}
      <div
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "10px",
          background: colors.gradient,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "12px",
          fontWeight: 700,
          color: "white",
          flexShrink: 0,
        }}
      >
        AI
      </div>

      {/* Status label + dots */}
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {status && (
          <span
            style={{
              fontSize: "12px",
              color: colors.textMuted,
              animation: "fadeIn 200ms ease-out",
            }}
          >
            {status}
          </span>
        )}

        <div
          style={{
            display: "flex",
            gap: "5px",
            padding: "14px 18px",
            backgroundColor: colors.agentBubble,
            border: `1px solid ${colors.border}`,
            borderRadius: "16px 16px 16px 4px",
            transition: "background-color 300ms ease",
          }}
        >
          <div style={dot(0)} />
          <div style={dot(0.15)} />
          <div style={dot(0.3)} />
        </div>
      </div>
    </div>
  );
}
