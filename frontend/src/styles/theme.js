// ─── COLOR PALETTES ─────────────────────────────
// Dark theme — deep dark with blue/purple accent (WCAG AA contrast)
export const darkColors = {
  bg: "#0c0c12",
  bgSecondary: "#14141f",
  surface: "#1a1a28",
  surfaceHover: "#22223a",
  border: "#2a2a3d",
  borderFocus: "#3b82f6",

  text: "#e8e8ed",
  textMuted: "#8888a0",
  textFaint: "#55556a",

  accent: "#3b82f6",
  accentGlow: "rgba(59,130,246,0.15)",
  gradient: "linear-gradient(135deg, #3b82f6, #8b5cf6)",

  userBubble: "#2563eb",
  agentBubble: "#1a1a28",

  success: "#22c55e",
  warning: "#f59e0b",
  error: "#ef4444",

  // MarkdownRenderer-specific
  codeBg: "#0d0d1a",
  codeHeader: "#1e1e2e",
  inlineCodeBg: "rgba(255,255,255,0.08)",
  hoverBg: "rgba(255,255,255,0.05)",
  sourceBg: "rgba(255,255,255,0.04)",
};

// Light theme — clean white with the same blue accent
export const lightColors = {
  bg: "#f8f9fb",
  bgSecondary: "#ffffff",
  surface: "#ffffff",
  surfaceHover: "#f0f1f4",
  border: "#d8dae0",
  borderFocus: "#3b82f6",

  text: "#1a1a2e",
  textMuted: "#5c5c72",
  textFaint: "#9494a8",

  accent: "#3b82f6",
  accentGlow: "rgba(59,130,246,0.12)",
  gradient: "linear-gradient(135deg, #3b82f6, #8b5cf6)",

  userBubble: "#2563eb",
  agentBubble: "#ffffff",

  success: "#16a34a",
  warning: "#d97706",
  error: "#dc2626",

  // MarkdownRenderer-specific
  codeBg: "#f4f4f8",
  codeHeader: "#e8e8ee",
  inlineCodeBg: "rgba(0,0,0,0.06)",
  hoverBg: "rgba(0,0,0,0.04)",
  sourceBg: "rgba(0,0,0,0.03)",
};

// Backwards-compatible default export — dark theme
// Components that haven't migrated to ThemeContext can still import this
export const colors = darkColors;

// ─── TYPOGRAPHY ──────────────────────────────────
export const fonts = {
  main: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "'Fira Code', 'Monaco', 'Consolas', monospace",
};

// ─── ANIMATION EASINGS ──────────────────────────
export const easings = {
  bouncy: "cubic-bezier(0.34, 1.56, 0.64, 1)",
  smooth: "cubic-bezier(0.25, 0.46, 0.45, 0.94)",
};

// ─── GLOBAL CSS (injected once at mount) ─────────
// Dynamic version that accepts a colors object for theme-aware body bg
export const buildGlobalCSS = (c) => `
@keyframes slideUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes typingDot {
  0%, 80%, 100% { opacity: .25; transform: scale(.85); }
  40%           { opacity: 1;   transform: scale(1); }
}
@keyframes pulseGlow {
  0%, 100% { box-shadow: 0 0 6px rgba(59,130,246,0.4); }
  50%      { box-shadow: 0 0 14px rgba(59,130,246,0.7); }
}
@keyframes cursorBlink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0; }
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: ${c.bg}; transition: background 300ms ease; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: ${c.border}; border-radius: 3px; }
`;

// Legacy static version (for any code that still imports globalCSS directly)
export const globalCSS = buildGlobalCSS(darkColors);

// ─── API CONFIG ──────────────────────────────────
// In Docker: empty string → requests go through nginx reverse proxy (same origin).
// In dev: set VITE_API_BASE=http://localhost:8000 in .env or shell.
export const API_BASE = import.meta.env.VITE_API_BASE || "";
