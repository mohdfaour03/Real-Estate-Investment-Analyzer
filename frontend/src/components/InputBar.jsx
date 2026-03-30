import { useState, useRef } from "react";
import { useTheme } from "../context/ThemeContext";
import useVoiceInput from "../hooks/useSpeechRecognition";
import VoiceButton from "./VoiceButton";

export default function InputBar({ onSend, disabled, onUploadPdf, isUploading }) {
  const [input, setInput] = useState("");
  const { colors } = useTheme();
  const textareaRef = useRef(null);
  const { isRecording, isTranscribing, audioLevel, analyserRef, startRecording, stopRecording } = useVoiceInput();
  const fileInputRef = useRef(null);

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file && onUploadPdf) onUploadPdf(file);
    e.target.value = ""; // reset so same file can be re-uploaded
  };

  const toggleMic = () => {
    if (isRecording) {
      stopRecording();
    } else if (!isTranscribing) {
      startRecording((text) => {
        setInput((prev) => (prev ? prev + " " + text : text));
        const el = textareaRef.current;
        if (el) {
          el.style.height = "auto";
          el.style.height = Math.min(el.scrollHeight, 140) + "px";
        }
      });
    }
  };

  const handleInput = (e) => {
    setInput(e.target.value);
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 140) + "px";
    }
  };

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSend(input.trim());
    setInput("");
    const el = textareaRef.current;
    if (el) el.style.height = "auto";
  };

  const hasText = input.trim().length > 0;

  return (
    <footer
      style={{
        padding: "14px 24px 8px",
        borderTop: `1px solid ${colors.border}`,
        background: `linear-gradient(0deg, ${colors.bg} 60%, transparent 100%)`,
        transition: "background 300ms ease",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          gap: "10px",
          maxWidth: "800px",
          margin: "0 auto",
          backgroundColor: colors.surface,
          border: `1px solid ${colors.border}`,
          borderRadius: "16px",
          padding: "6px 6px 6px 10px",
          transition: "border-color 200ms ease, background-color 300ms ease",
        }}
        onFocus={(e) =>
          (e.currentTarget.style.borderColor = colors.borderFocus)
        }
        onBlur={(e) => (e.currentTarget.style.borderColor = colors.border)}
      >
        {/* Upload button — left of text area */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading || disabled}
          aria-label="Upload PDF document"
          title="Upload PDF to knowledge base"
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            border: `1px solid ${isUploading ? colors.accent + "44" : colors.border}`,
            background: isUploading ? colors.accent + "15" : "transparent",
            color: isUploading ? colors.accent : colors.textMuted,
            fontSize: "15px",
            cursor: isUploading ? "default" : "pointer",
            transition: "all 200ms ease",
            flexShrink: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onMouseEnter={(e) => {
            if (!isUploading) e.currentTarget.style.borderColor = colors.accent;
          }}
          onMouseLeave={(e) => {
            if (!isUploading) e.currentTarget.style.borderColor = colors.border;
          }}
        >
          {isUploading ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: "spin 1s linear infinite" }}>
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="2" strokeDasharray="28" strokeDashoffset="8" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 10v2.667A1.334 1.334 0 0 1 12.667 14H3.333A1.334 1.334 0 0 1 2 12.667V10"/>
              <polyline points="5 5.333 8 2 11 5.333"/>
              <line x1="8" y1="2" x2="8" y2="10.667"/>
            </svg>
          )}
        </button>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          placeholder={isRecording ? "Listening..." : isTranscribing ? "Transcribing..." : "Ask about UAE rental properties..."}
          aria-label="Type your question about UAE rental properties"
          rows={1}
          style={{
            flex: 1,
            background: "none",
            border: "none",
            outline: "none",
            color: colors.text,
            fontSize: "14px",
            padding: "8px 0",
            resize: "none",
            lineHeight: "1.5",
            maxHeight: "140px",
            fontFamily: "inherit",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
        />
        <VoiceButton
          isRecording={isRecording}
          isTranscribing={isTranscribing}
          audioLevel={audioLevel}
          analyserRef={analyserRef}
          onClick={toggleMic}
        />
        <button
          onClick={handleSend}
          disabled={!hasText || disabled}
          aria-label="Send message"
          style={{
            padding: "10px 22px",
            borderRadius: "12px",
            border: "none",
            background: hasText ? colors.gradient : colors.surfaceHover,
            color: hasText ? "white" : colors.textFaint,
            fontSize: "13px",
            fontWeight: 600,
            cursor: hasText ? "pointer" : "default",
            transition: "all 200ms ease",
            letterSpacing: "0.2px",
            flexShrink: 0,
          }}
        >
          Send
        </button>
      </div>
    </footer>
  );
}
