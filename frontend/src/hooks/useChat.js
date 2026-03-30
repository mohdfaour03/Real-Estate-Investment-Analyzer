import { useState, useCallback, useRef } from "react";
import { API_BASE } from "../styles/theme";

// Persistent session ID so the backend can track conversation history
let sessionId = crypto.randomUUID();

// Generates a unique ID for each message
let msgId = 0;
const nextId = () => ++msgId;

// Creates a timestamp string like "2:34 PM"
const now = () =>
  new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

/**
 * useChat — manages conversation state and SSE streaming to Agent System A.
 *
 * Returns:
 *   messages  — array of { id, role, content, timestamp, sources, agentPath }
 *   isLoading — true while waiting for / streaming AI response
 *   error     — string if last request failed, null otherwise
 *   sendMessage(text) — sends user query to backend
 *   resetChat() — clears messages and starts fresh session
 *   retryLast() — re-sends the last user query
 *   lastUserQuery — the most recent user query (for retry)
 */
const AGENT_B_BASE = import.meta.env.VITE_AGENT_B_BASE || "http://localhost:8001";

export default function useChat() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [thinkingStatus, setThinkingStatus] = useState(null);
  const [activeAgent, setActiveAgent] = useState("A"); // "A" or "B"
  // Track last user query for retry functionality
  const lastUserQueryRef = useRef(null);
  // Ref to allow cancellation of in-flight stream
  const abortRef = useRef(null);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || isLoading) return;

    // Track last query for retry
    lastUserQueryRef.current = text.trim();

    // 1. Add user message to state
    const userMsg = {
      id: nextId(),
      role: "user",
      content: text,
      timestamp: now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);
    setError(null);

    // 2. Prepare a placeholder for the AI response (starts empty, fills via SSE)
    const aiId = nextId();
    const aiMsg = {
      id: aiId,
      role: "assistant",
      content: "",
      timestamp: now(),
      sources: [],
      agentPath: [],
    };
    setMessages((prev) => [...prev, aiMsg]);

    // 3a. Agent B: non-streaming (it only has POST /chat)
    if (activeAgent === "B") {
      try {
        setThinkingStatus("Agent B analyzing...");
        const res = await fetch(`${AGENT_B_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: text, session_id: sessionId }),
        });
        const data = await res.json();
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiId ? { ...m, content: data.response || "No response." } : m
          )
        );
      } catch (err) {
        setError(err.message || "Agent B request failed");
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiId ? { ...m, content: "Agent B is unavailable." } : m
          )
        );
      } finally {
        setIsLoading(false);
        setThinkingStatus(null);
      }
      return;
    }

    // 3b. Agent A: SSE streaming to /chat/stream
    try {
      const controller = new AbortController();
      abortRef.current = controller;

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, session_id: sessionId }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE format: lines starting with "data: " separated by double newlines
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = line.slice(6).trim();

          // "[DONE]" signals stream end
          if (data === "[DONE]") continue;

          try {
            const parsed = JSON.parse(data);

            if (parsed.type === "status") {
              setThinkingStatus(parsed.message || null);
            } else if (parsed.token || parsed.content) {
              setThinkingStatus(null); // clear status once tokens flow
              const chunk = parsed.token || parsed.content || "";
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiId ? { ...m, content: m.content + chunk } : m
                )
              );
            } else if (parsed.type === "sources") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiId ? { ...m, sources: parsed.data } : m
                )
              );
            } else if (parsed.type === "agents") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiId ? { ...m, agentPath: parsed.data } : m
                )
              );
            } else if (parsed.type === "error") {
              setError(parsed.message);
            } else if (typeof parsed === "string") {
              // Plain string token
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiId ? { ...m, content: m.content + parsed } : m
                )
              );
            }
          } catch {
            // If JSON parse fails, treat the raw data as a text token
            setMessages((prev) =>
              prev.map((m) =>
                m.id === aiId ? { ...m, content: m.content + data } : m
              )
            );
          }
        }
      }
    } catch (err) {
      if (err.name === "AbortError") return; // user cancelled, not an error

      console.error("Chat stream error:", err);

      // Distinguish connection drops from server errors for clearer UX
      const isNetworkError = err instanceof TypeError || err.message?.includes("network");
      const errorMsg = isNetworkError
        ? "Connection lost. Please check that backend services are running."
        : (err.message || "Failed to get response");
      setError(errorMsg);

      // If stream failed or dropped mid-response, update the AI message
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== aiId) return m;
          // No content at all → full failure message
          if (!m.content) return { ...m, content: "Sorry, I couldn't process your request. Please check that all backend services are running and try again." };
          // Partial content → append a visible indicator that the stream was interrupted
          return { ...m, content: m.content + "\n\n*[Response interrupted — click Retry below]*" };
        })
      );
    } finally {
      setIsLoading(false);
      setThinkingStatus(null);
      abortRef.current = null;
    }
  }, [isLoading]);

  // Clears conversation and generates a new session ID
  const resetChat = useCallback(() => {
    // Cancel any in-flight stream
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setMessages([]);
    setIsLoading(false);
    setError(null);
    setThinkingStatus(null);
    lastUserQueryRef.current = null;
    sessionId = crypto.randomUUID();
  }, []);

  // Re-sends the last user query
  const retryLast = useCallback(() => {
    if (lastUserQueryRef.current && !isLoading) {
      // Remove the failed AI response (last message) before retrying
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant") {
          return prev.slice(0, -1);
        }
        return prev;
      });
      setError(null);
      // Small delay so state updates before re-send
      setTimeout(() => sendMessage(lastUserQueryRef.current), 50);
    }
  }, [isLoading, sendMessage]);

  const [isUploading, setIsUploading] = useState(false);

  const uploadPdf = useCallback(async (file) => {
    setIsUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("session_id", sessionId);

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 120000); // 2 min timeout

      const res = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeout);

      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Upload failed");

      // Show confirmation message in chat
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          role: "assistant",
          content: `**${data.filename}** uploaded successfully (${data.chunks_ingested} chunks indexed). You can now ask questions about this document.`,
          timestamp: now(),
        },
      ]);

      return data;
    } catch (err) {
      const msg = err.name === "AbortError"
        ? "PDF upload timed out. The file may be too large."
        : (err.message || "PDF upload failed");
      setError(msg);
      return null;
    } finally {
      setIsUploading(false);
    }
  }, []);

  return { messages, isLoading, isUploading, error, thinkingStatus, sendMessage, resetChat, retryLast, uploadPdf, activeAgent, setActiveAgent };
}
