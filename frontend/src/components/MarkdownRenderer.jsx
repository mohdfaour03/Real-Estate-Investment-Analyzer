import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useState, useEffect, useRef, memo } from "react";
import { fonts } from "../styles/theme";
import { useTheme } from "../context/ThemeContext";

function CodeBlock({ children, className }) {
  const [copied, setCopied] = useState(false);
  const { colors, isDark } = useTheme();
  const timerRef = useRef(null);
  const language = className ? className.replace("language-", "") : "text";
  const code = String(children).replace(/\n$/, "");

  // Cleanup timeout on unmount to prevent setState on unmounted component
  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ position: "relative", margin: "12px 0", borderRadius: "10px", overflow: "hidden" }}>
      {/* Language label + copy button */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: "6px 14px", backgroundColor: colors.codeHeader,
        borderBottom: `1px solid ${colors.border}`, fontSize: "11px",
      }}>
        <span style={{ color: colors.textFaint, textTransform: "uppercase", letterSpacing: "0.5px" }}>
          {language}
        </span>
        <button onClick={handleCopy} aria-label="Copy code" style={{
          background: "none", border: "none", color: copied ? colors.success : colors.textFaint,
          cursor: "pointer", fontSize: "11px", transition: "color 150ms ease",
        }}>
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={isDark ? oneDark : oneLight}
        customStyle={{
          margin: 0, padding: "14px", fontSize: "13px",
          background: colors.codeBg, fontFamily: fonts.mono,
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// Memoized to prevent re-renders of every message when new tokens stream in
const MarkdownRenderer = memo(function MarkdownRenderer({ content }) {
  const { colors } = useTheme();

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // ── Code blocks ──
        code({ inline, className, children }) {
          if (!inline && className) {
            return <CodeBlock className={className}>{children}</CodeBlock>;
          }
          // Inline code
          return (
            <code style={{
              background: colors.inlineCodeBg, padding: "2px 6px",
              borderRadius: "4px", fontSize: "12px", fontFamily: fonts.mono,
            }}>{children}</code>
          );
        },

        // ── Tables ──
        table({ children }) {
          return (
            <div style={{ overflowX: "auto", margin: "12px 0" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                {children}
              </table>
            </div>
          );
        },
        th({ children }) {
          return (
            <th style={{
              padding: "8px 12px", textAlign: "left",
              borderBottom: `2px solid ${colors.border}`,
              color: colors.text, fontWeight: 600, fontSize: "12px",
              textTransform: "uppercase", letterSpacing: "0.5px",
            }}>{children}</th>
          );
        },
        td({ children }) {
          return (
            <td style={{
              padding: "7px 12px",
              borderBottom: `1px solid ${colors.border}`,
              color: colors.textMuted, fontSize: "13px",
            }}>{children}</td>
          );
        },

        // ── Headings ──
        h3({ children }) {
          return (
            <h3 style={{
              margin: "16px 0 6px", fontSize: "13px", fontWeight: 700,
              color: colors.accent, textTransform: "uppercase", letterSpacing: "0.8px",
            }}>{children}</h3>
          );
        },
        h2({ children }) {
          return (
            <h2 style={{
              margin: "16px 0 6px", fontSize: "15px", fontWeight: 700, color: colors.text,
            }}>{children}</h2>
          );
        },

        // ── Blockquotes ──
        blockquote({ children }) {
          return (
            <blockquote style={{
              borderLeft: `3px solid ${colors.accent}`, paddingLeft: "12px",
              margin: "8px 0", color: colors.textMuted, fontStyle: "italic", fontSize: "13px",
            }}>{children}</blockquote>
          );
        },

        // ── Paragraphs ──
        p({ children }) {
          return (
            <p style={{ margin: "4px 0", lineHeight: "1.7", fontSize: "14px", color: colors.text }}>
              {children}
            </p>
          );
        },

        // ── Bold ──
        strong({ children }) {
          return <strong style={{ color: colors.text, fontWeight: 600 }}>{children}</strong>;
        },

        // ── Lists ──
        ul({ children }) {
          return <ul style={{ margin: "8px 0", paddingLeft: "20px", color: colors.textMuted, fontSize: "14px", lineHeight: "1.7" }}>{children}</ul>;
        },
        ol({ children }) {
          return <ol style={{ margin: "8px 0", paddingLeft: "20px", color: colors.textMuted, fontSize: "14px", lineHeight: "1.7" }}>{children}</ol>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

export default MarkdownRenderer;
