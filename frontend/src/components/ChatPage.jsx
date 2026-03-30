import { useEffect, useRef } from "react";
import useChat from "../hooks/useChat";
import { useTheme } from "../context/ThemeContext";
import { fonts, buildGlobalCSS } from "../styles/theme";
import Header from "./Header";
import ChatMessage from "./ChatMessage";
import TypingIndicator from "./TypingIndicator";
import SuggestionChips from "./SuggestionChips";
import InputBar from "./InputBar";

// Feature cards shown on the welcome screen to communicate system capabilities
const FEATURES = [
  { icon: "🔍", title: "Search 73K+ Listings", desc: "Filter UAE rental properties by area, beds, rent, and furnishing" },
  { icon: "📊", title: "Compare Areas & Yields", desc: "Side-by-side analysis with market data and appreciation trends" },
  { icon: "🏦", title: "UAE Mortgage Calculator", desc: "Emirate-specific rates, down payments, and DTI assessment" },
];

export default function ChatPage() {
  const { messages, isLoading, isUploading, error, thinkingStatus, sendMessage, resetChat, retryLast, uploadPdf, activeAgent, setActiveAgent } = useChat();
  const { colors } = useTheme();
  const messagesEndRef = useRef(null);

  // Inject global CSS (keyframes, scrollbar, reset) — re-inject when theme changes
  useEffect(() => {
    const style = document.createElement("style");
    style.setAttribute("data-theme-css", "true");
    style.textContent = buildGlobalCSS(colors);
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, [colors]);

  // Auto-scroll to bottom when new messages arrive or typing starts
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Send a message (from input bar or suggestion chip click)
  const handleSend = (text) => {
    sendMessage(text);
  };

  // Show suggestion chips only when conversation is empty (first-time UX)
  const showSuggestions = messages.length === 0 && !isLoading;

  // Determine if the last AI message is still streaming (has content but isLoading)
  const lastMsg = messages[messages.length - 1];
  const streamingMsgId = isLoading && lastMsg && lastMsg.role === "assistant" && lastMsg.content
    ? lastMsg.id
    : null;

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      backgroundColor: colors.bg,
      color: colors.text,
      fontFamily: fonts.main,
      transition: "background-color 300ms ease, color 300ms ease",
    }}>
      {/* ── Sticky header with logo + theme toggle + New Chat button ── */}
      <Header
          onNewChat={resetChat}
          activeAgent={activeAgent}
          onToggleAgent={() => { setActiveAgent(activeAgent === "A" ? "B" : "A"); resetChat(); }}
        />

      {/* ── Messages area ── */}
      <main style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        gap: "20px",
      }}>
        {/* Welcome state — shown when no messages yet */}
        {messages.length === 0 && !isLoading && (
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", flex: 1, gap: "16px",
            animation: "fadeIn 500ms ease-out",
          }}>
            <div style={{
              width: "56px", height: "56px", borderRadius: "16px",
              background: colors.gradient, display: "flex", alignItems: "center",
              justifyContent: "center", fontSize: "22px", fontWeight: 800, color: "white",
            }}>RE</div>
            <h2 style={{
              color: colors.text, fontSize: "20px", fontWeight: 600, margin: 0,
            }}>
              How can I help you invest?
            </h2>
            <p style={{
              color: colors.textMuted, fontSize: "14px", maxWidth: "400px",
              textAlign: "center", lineHeight: "1.6",
            }}>
              Ask me about UAE rental properties, investment yields,
              mortgage calculations, or area comparisons.
            </p>

            {/* Feature cards — shows what the system can do at a glance */}
            <div style={{
              display: "flex", gap: "12px", marginTop: "8px",
              flexWrap: "wrap", justifyContent: "center",
              maxWidth: "640px",
            }}>
              {FEATURES.map((f, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: "10px",
                  padding: "14px 16px", borderRadius: "12px",
                  backgroundColor: colors.surface,
                  border: `1px solid ${colors.border}`,
                  flex: "1 1 180px", maxWidth: "200px",
                  transition: "border-color 200ms ease, background-color 300ms ease",
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = colors.accent}
                onMouseLeave={e => e.currentTarget.style.borderColor = colors.border}
                >
                  <span style={{ fontSize: "20px", lineHeight: 1, flexShrink: 0 }}>{f.icon}</span>
                  <div>
                    <div style={{
                      fontSize: "12px", fontWeight: 600, color: colors.text,
                      marginBottom: "4px",
                    }}>{f.title}</div>
                    <div style={{
                      fontSize: "11px", color: colors.textMuted, lineHeight: "1.4",
                    }}>{f.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Message list */}
        {messages.map((msg) =>
          msg.role === "user" || msg.content ? (
            <ChatMessage
              key={msg.id}
              message={msg}
              isStreaming={msg.id === streamingMsgId}
            />
          ) : null
        )}

        {/* Typing indicator — only while waiting for first token */}
        {isLoading && (() => {
          const last = messages[messages.length - 1];
          return !last || last.role === "user" || !last.content;
        })() && <TypingIndicator status={thinkingStatus} />}

        {/* Error banner with retry button */}
        {error && (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 16px", borderRadius: "10px",
            backgroundColor: "rgba(239,68,68,0.1)",
            border: `1px solid ${colors.error}33`,
            animation: "fadeIn 200ms ease-out",
          }}>
            <span style={{ color: colors.error, fontSize: "13px" }}>{error}</span>
            <button
              onClick={retryLast}
              aria-label="Retry last message"
              style={{
                padding: "6px 14px", borderRadius: "8px",
                border: `1px solid ${colors.error}44`,
                backgroundColor: "transparent",
                color: colors.error, fontSize: "12px", fontWeight: 500,
                cursor: "pointer", transition: "all 150ms ease",
                fontFamily: "inherit", flexShrink: 0, marginLeft: "12px",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.backgroundColor = "rgba(239,68,68,0.15)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              ↻ Retry
            </button>
          </div>
        )}

        {/* Invisible scroll anchor */}
        <div ref={messagesEndRef} />
      </main>

      {/* ── Suggestion chips (only on empty state) ── */}
      <SuggestionChips visible={showSuggestions} onSelect={handleSend} />

      {/* ── Input bar + disclaimer ── */}
      <InputBar onSend={handleSend} disabled={isLoading} onUploadPdf={uploadPdf} isUploading={isUploading} />

      {/* ── Disclaimer ── */}
      <div style={{
        textAlign: "center",
        padding: "0 24px 12px",
        fontSize: "11px",
        color: colors.textFaint,
        letterSpacing: "0.1px",
      }}>
        AI can make mistakes. Always verify important information.
      </div>
    </div>
  );
}
