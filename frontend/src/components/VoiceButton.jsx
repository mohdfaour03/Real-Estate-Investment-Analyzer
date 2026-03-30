import { useRef, useEffect } from "react";
import { useTheme } from "../context/ThemeContext";

const MicIcon = ({ color, size = 18 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="9" y="1" width="6" height="12" rx="3" />
    <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const StopIcon = ({ color, size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
    <rect x="4" y="4" width="16" height="16" rx="3" />
  </svg>
);

/**
 * Waveform — draws horizontal frequency bars on a Canvas.
 * Reads directly from the AnalyserNode ref (~60fps) via its own
 * requestAnimationFrame loop, so it doesn't trigger React re-renders.
 */
function Waveform({ analyserRef, barColor, width, height }) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const analyser = analyserRef.current;
    if (!canvas || !analyser) return;

    const ctx = canvas.getContext("2d");
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const BAR_COUNT = 24;
    const BAR_GAP = 2;
    const BAR_WIDTH = (width - BAR_GAP * (BAR_COUNT - 1)) / BAR_COUNT;
    const MIN_HEIGHT = 2;
    const RADIUS = Math.min(BAR_WIDTH / 2, 2);

    const draw = () => {
      analyser.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, width, height);

      // Sample BAR_COUNT evenly-spaced bins from the frequency data
      const step = Math.floor(dataArray.length / BAR_COUNT);

      for (let i = 0; i < BAR_COUNT; i++) {
        const value = dataArray[i * step] / 255;
        const barH = Math.max(MIN_HEIGHT, value * height * 0.9);
        const x = i * (BAR_WIDTH + BAR_GAP);
        const y = (height - barH) / 2; // center vertically

        ctx.beginPath();
        ctx.roundRect(x, y, BAR_WIDTH, barH, RADIUS);
        ctx.fillStyle = barColor;
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [analyserRef, barColor, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ display: "block" }}
    />
  );
}

export default function VoiceButton({ isRecording, isTranscribing, audioLevel, analyserRef, onClick }) {
  const { colors } = useTheme();

  const isIdle = !isRecording && !isTranscribing;

  // Idle: compact circle. Recording: expands to pill with waveform inside.
  const IDLE_SIZE = 42;
  const RECORDING_WIDTH = 120;
  const RECORDING_HEIGHT = 42;

  return (
    <div style={{
      position: "relative",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}>
      <button
        onClick={onClick}
        disabled={isTranscribing}
        aria-label={isRecording ? "Stop recording" : isTranscribing ? "Transcribing..." : "Start voice input"}
        style={{
          width: isRecording ? `${RECORDING_WIDTH}px` : `${IDLE_SIZE}px`,
          height: `${isRecording ? RECORDING_HEIGHT : IDLE_SIZE}px`,
          borderRadius: isRecording ? "21px" : "50%",
          border: isIdle ? `1.5px solid ${colors.border}` : "none",
          background: isRecording
            ? `rgba(239, 68, 68, ${0.12 + audioLevel * 0.1})`
            : isTranscribing
              ? colors.surfaceHover
              : colors.surface,
          cursor: isTranscribing ? "wait" : "pointer",
          transition: "all 250ms cubic-bezier(0.4, 0, 0.2, 1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "8px",
          padding: isRecording ? "0 12px" : "0",
          position: "relative",
          zIndex: 1,
          boxShadow: isRecording
            ? `0 0 ${6 + audioLevel * 16}px rgba(239, 68, 68, ${0.15 + audioLevel * 0.25})`
            : "none",
          overflow: "hidden",
        }}
        onMouseEnter={(e) => {
          if (isIdle) e.currentTarget.style.borderColor = colors.accent;
        }}
        onMouseLeave={(e) => {
          if (isIdle) e.currentTarget.style.borderColor = colors.border;
        }}
      >
        {isRecording ? (
          <>
            <Waveform
              analyserRef={analyserRef}
              barColor="rgba(239, 68, 68, 0.8)"
              width={72}
              height={28}
            />
            <StopIcon color="#ef4444" size={14} />
          </>
        ) : isTranscribing ? (
          <div style={{
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            border: "2px solid transparent",
            borderTopColor: colors.accent,
            borderRightColor: colors.accent,
            animation: "voiceSpin 0.8s linear infinite",
          }} />
        ) : (
          <MicIcon color={colors.textMuted} />
        )}
      </button>

      <style>{`
        @keyframes voiceSpin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
