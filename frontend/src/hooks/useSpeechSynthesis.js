import { useState, useCallback, useEffect } from "react";

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, "")        // code blocks
    .replace(/`([^`]+)`/g, "$1")            // inline code
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1") // links — keep text
    .replace(/#{1,6}\s+/g, "")              // headings
    .replace(/\*\*([^*]+)\*\*/g, "$1")      // bold
    .replace(/\*([^*]+)\*/g, "$1")          // italic
    .replace(/^\s*[-*]\s+/gm, "")           // list bullets
    .replace(/\|[^\n]+\|/g, "")             // table rows
    .replace(/[-:]{3,}/g, "")               // table separators
    .replace(/\n{2,}/g, ". ")               // collapse blank lines
    .trim();
}

export default function useSpeechSynthesis() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  const speak = useCallback((text) => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(stripMarkdown(text));
    utterance.lang = "en-US";
    utterance.rate = 1.0;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }, [isSupported]);

  const stop = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [isSupported]);

  useEffect(() => {
    return () => { if (isSupported) window.speechSynthesis.cancel(); };
  }, [isSupported]);

  return { isSpeaking, isSupported, speak, stop };
}
