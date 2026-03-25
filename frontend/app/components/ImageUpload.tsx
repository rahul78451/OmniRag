"use client";
import { useRef, useState } from "react";

interface ImageUploadProps {
  onImage: (file: File, prompt: string) => void;
  disabled?: boolean;
}

export default function ImageUpload({ onImage, disabled }: ImageUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [prompt, setPrompt] = useState("");
  const [showPrompt, setShowPrompt] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setShowPrompt(true);
  }

  function handleSend() {
    if (!pendingFile) return;
    onImage(pendingFile, prompt || "What do you see in this image? How does it relate to my documents?");
    setPendingFile(null);
    setPrompt("");
    setShowPrompt(false);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        title="Upload image or PDF"
        style={{
          width: 48,
          height: 48,
          borderRadius: "50%",
          border: "1px solid #d1d5db",
          cursor: disabled ? "not-allowed" : "pointer",
          background: "white",
          fontSize: 20,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: disabled ? 0.4 : 1,
          flexShrink: 0,
        }}
      >
        📎
      </button>
      <input
        ref={inputRef}
        type="file"
        accept="image/*,.pdf"
        style={{ display: "none" }}
        onChange={handleFile}
      />

      {showPrompt && (
        <div
          style={{
            position: "absolute",
            bottom: 56,
            left: 0,
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: 10,
            padding: "0.75rem",
            width: 280,
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
            zIndex: 10,
          }}
        >
          <p style={{ margin: "0 0 0.5rem", fontSize: 13, fontWeight: 500 }}>
            📎 {pendingFile?.name}
          </p>
          <input
            placeholder="What should I look for? (optional)"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            style={{
              width: "100%",
              padding: "0.4rem 0.6rem",
              borderRadius: 6,
              border: "1px solid #d1d5db",
              fontSize: 13,
              marginBottom: "0.5rem",
              boxSizing: "border-box",
            }}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            autoFocus
          />
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              onClick={handleSend}
              style={{
                flex: 1,
                padding: "0.4rem",
                borderRadius: 6,
                background: "#7c3aed",
                color: "white",
                border: "none",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Send
            </button>
            <button
              onClick={() => { setShowPrompt(false); setPendingFile(null); }}
              style={{
                padding: "0.4rem 0.8rem",
                borderRadius: 6,
                border: "1px solid #d1d5db",
                background: "white",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
