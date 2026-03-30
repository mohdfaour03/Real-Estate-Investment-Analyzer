import { useState, memo } from "react";
import MarkdownRenderer from "./MarkdownRenderer";
import SourceChips from "./SourceChips";
import MessageActions from "./MessageActions";
import { useTheme } from "../context/ThemeContext";

/**
 * ChatMessage — renders a single user or AI message bubble.
 * Memoized so non-streaming messages don't re-render when new tokens arrive.
 *
 * Props:
 *   message    — { id, role, content, timestamp, sources }
 *   isStreaming — true if this message is still receiving tokens (shows blinking cursor)
 */
const ChatMessage = memo(function ChatMessage({ message, isStreaming }) {
  const [hovered, setHovered] = useState(false);
  const { colors } = useTheme();
  const isUser = message.role === "user";

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        gap: "10px",
        alignItems: "flex-start",
        animation: "slideUp 350ms cubic-bezier(0.34,1.56,0.64,1) forwards",
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* AI avatar — left side */}
      {!isUser && (
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
            flexShrink: 0,
            color: "white",
          }}
        >
          AI
        </div>
      )}

      {/* Message body */}
      <div
        style={{ maxWidth: "720px", display: "flex", flexDirection: "column" }}
      >
        {/* Timestamp */}
        <span
          style={{
            fontSize: "10px",
            color: colors.textFaint,
            marginBottom: "4px",
            alignSelf: isUser ? "flex-end" : "flex-start",
          }}
        >
          {message.timestamp}
        </span>

        {/* Bubble */}
        <div
          style={{
            borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
            padding: isUser ? "12px 18px" : "16px 20px",
            backgroundColor: isUser ? colors.userBubble : colors.agentBubble,
            color: isUser ? "#ffffff" : colors.text,
            border: isUser ? "none" : `1px solid ${colors.border}`,
            transition: "border-color 200ms ease, background-color 300ms ease",
            ...(!isUser && hovered
              ? { borderColor: "rgba(59,130,246,0.3)" }
              : {}),
          }}
        >
          {isUser ? (
            <p style={{ margin: 0, fontSize: "14px", lineHeight: "1.6" }}>
              {message.content}
            </p>
          ) : (
            <>
              <MarkdownRenderer content={message.content} />
              {/* Blinking cursor while tokens are still streaming */}
              {isStreaming && (
                <span
                  style={{
                    display: "inline-block",
                    width: "2px",
                    height: "16px",
                    backgroundColor: colors.accent,
                    marginLeft: "2px",
                    verticalAlign: "text-bottom",
                    animation: "cursorBlink 1s step-end infinite",
                  }}
                />
              )}
            </>
          )}
        </div>

        {/* AI-only extras: sources, actions */}
        {!isUser && <SourceChips sources={message.sources} />}
        {!isUser && hovered && !isStreaming && (
          <MessageActions
            onCopy={() => navigator.clipboard?.writeText(message.content)}
            messageContent={message.content}
          />
        )}
      </div>

      {/* User avatar — right side */}
      {isUser && (
        <div
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "10px",
            backgroundColor: colors.userBubble,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: "12px",
            fontWeight: 600,
            flexShrink: 0,
            color: "white",
          }}
        >
          MF
        </div>
      )}
    </div>
  );
});

export default ChatMessage;
