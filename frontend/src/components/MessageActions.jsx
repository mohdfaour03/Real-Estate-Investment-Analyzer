import { useState, useEffect, useRef } from "react";
import { useTheme } from "../context/ThemeContext";
import useSpeechSynthesis from "../hooks/useSpeechSynthesis";

export default function MessageActions({ onCopy, messageContent }) {
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState(null);
  const { colors } = useTheme();
  const timerRef = useRef(null);

  // Cleanup timeout on unmount to prevent setState on unmounted component
  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const { isSpeaking, isSupported: ttsSupported, speak, stop } = useSpeechSynthesis();

  const handleCopy = () => {
    setCopied(true);
    onCopy?.();
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
  };

  const btnStyle = (active) => ({
    background: "none", border: "none", cursor: "pointer",
    padding: "4px 6px", borderRadius: "6px",
    color: active ? colors.accent : colors.textFaint,
    fontSize: "13px", transition: "all 150ms ease",
    display: "flex", alignItems: "center",
  });

  return (
    <div style={{
      display: "flex", gap: "2px", marginTop: "6px",
      animation: "fadeIn 200ms ease-out",
    }}>
      {ttsSupported && (
        <button style={btnStyle(isSpeaking)}
          onClick={() => isSpeaking ? stop() : speak(messageContent)}
          aria-label={isSpeaking ? "Stop speaking" : "Read message aloud"}
          onMouseEnter={e => e.target.style.backgroundColor = colors.hoverBg}
          onMouseLeave={e => e.target.style.backgroundColor = "transparent"}
        >{isSpeaking ? "◼ Stop" : "🔊 Speak"}</button>
      )}
      <button style={btnStyle(copied)} onClick={handleCopy} aria-label="Copy message"
        onMouseEnter={e => e.target.style.backgroundColor = colors.hoverBg}
        onMouseLeave={e => e.target.style.backgroundColor = "transparent"}
      >{copied ? "✓ Copied" : "⧉ Copy"}</button>
      <button style={btnStyle(liked === "up")} aria-label="Thumbs up"
        onClick={() => setLiked(liked === "up" ? null : "up")}
        onMouseEnter={e => e.target.style.backgroundColor = colors.hoverBg}
        onMouseLeave={e => e.target.style.backgroundColor = "transparent"}
      >▲</button>
      <button style={btnStyle(liked === "down")} aria-label="Thumbs down"
        onClick={() => setLiked(liked === "down" ? null : "down")}
        onMouseEnter={e => e.target.style.backgroundColor = colors.hoverBg}
        onMouseLeave={e => e.target.style.backgroundColor = "transparent"}
      >▼</button>
    </div>
  );
}
