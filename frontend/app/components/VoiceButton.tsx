"use client";

interface VoiceButtonProps {
  isListening: boolean;
  onStart: () => void;
  onStop: () => void;
  disabled?: boolean;
}

export default function VoiceButton({
  isListening,
  onStart,
  onStop,
  disabled,
}: VoiceButtonProps) {
  return (
    <button
      onClick={isListening ? onStop : onStart}
      disabled={disabled}
      title={isListening ? "Stop listening" : "Start voice input"}
      style={{
        width: 48,
        height: 48,
        borderRadius: "50%",
        border: "none",
        cursor: disabled ? "not-allowed" : "pointer",
        background: isListening ? "#ef4444" : "#7c3aed",
        color: "white",
        fontSize: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: isListening ? "0 0 0 4px rgba(239,68,68,0.25)" : "none",
        transition: "all 0.2s",
        opacity: disabled ? 0.4 : 1,
        flexShrink: 0,
      }}
    >
      {isListening ? "⏹" : "🎙️"}
    </button>
  );
}
