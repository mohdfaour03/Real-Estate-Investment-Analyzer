import { useState, useRef, useCallback, useEffect } from "react";
import { API_BASE } from "../styles/theme";

export default function useVoiceInput() {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const onResultRef = useRef(null);

  const startLevelMonitor = useCallback((stream) => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.4;
    audioContextRef.current = audioContext;
    analyserRef.current = analyser;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        sum += dataArray[i] * dataArray[i];
      }
      const rms = Math.sqrt(sum / dataArray.length) / 255;
      setAudioLevel(Math.min(1, rms * 1.8));
      rafRef.current = requestAnimationFrame(tick);
    };
    tick();
  }, []);

  const stopLevelMonitor = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    if (audioContextRef.current) audioContextRef.current.close();
    audioContextRef.current = null;
    analyserRef.current = null;
    setAudioLevel(0);
  }, []);

  const startRecording = useCallback(async (onResult) => {
    onResultRef.current = onResult;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      startLevelMonitor(stream);

      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      const chunks = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stopLevelMonitor();
        stream.getTracks().forEach((t) => t.stop());

        const blob = new Blob(chunks, { type: "audio/webm" });
        if (blob.size < 100) return;

        setIsTranscribing(true);

        try {
          const formData = new FormData();
          formData.append("file", blob, "recording.webm");

          const res = await fetch(`${API_BASE}/transcribe`, {
            method: "POST",
            body: formData,
          });
          const data = await res.json();

          if (data.text && onResultRef.current) {
            onResultRef.current(data.text);
          }
        } catch (err) {
          console.error("Transcription request failed:", err);
        } finally {
          setIsTranscribing(false);
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access denied:", err);
    }
  }, [startLevelMonitor, stopLevelMonitor]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  useEffect(() => {
    return () => {
      stopLevelMonitor();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [stopLevelMonitor]);

  return {
    isRecording,
    isTranscribing,
    isActive: isRecording || isTranscribing,
    audioLevel,
    analyserRef,
    startRecording,
    stopRecording,
  };
}
