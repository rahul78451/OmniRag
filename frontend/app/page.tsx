"use client";
import { useState, useRef, useEffect, useCallback } from "react";
import VoiceButton from "./components/VoiceButton";
import ImageUpload from "./components/ImageUpload";
import ResponseStream from "./components/ResponseStream";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8080";
const WS_URL = BACKEND_URL.replace("https://", "wss://").replace(
  "http://",
  "ws://"
);

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("disconnected"); // disconnected | connecting | connected | retrieving
  const [isListening, setIsListening] = useState(false);
  const [textInput, setTextInput] = useState("");
  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const processorRef = useRef(null);
  const audioQueueRef = useRef([]);
  const isPlayingRef = useRef(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Connect WebSocket ──────────────────────────────────
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setStatus("connecting");

    const ws = new WebSocket(`${WS_URL}/ws/live`);
    wsRef.current = ws;

    ws.onopen = () => setStatus("connected");
    ws.onclose = () => {
      setStatus("disconnected");
      setIsListening(false);
    };
    ws.onerror = () => setStatus("disconnected");

    ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "text") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && !last.complete) {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + data.content },
            ];
          }
          return [
            ...prev,
            { role: "assistant", content: data.content, complete: false },
          ];
        });
      } else if (data.type === "turn_complete") {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant") {
            return [...prev.slice(0, -1), { ...last, complete: true }];
          }
          return prev;
        });
        setStatus("connected");
      } else if (data.type === "audio") {
        const audioData = base64ToFloat32(data.data);
        audioQueueRef.current.push(audioData);
        if (!isPlayingRef.current) playAudioQueue();
      } else if (data.type === "retrieving") {
        setStatus("retrieving");
        setMessages((prev) => [
          ...prev,
          {
            role: "system",
            content: `Searching knowledge base for: "${data.query}"`,
          },
        ]);
      } else if (data.type === "status") {
        if (data.content === "connected") {
          setMessages([
            {
              role: "assistant",
              content: data.message,
              complete: true,
            },
          ]);
        }
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  // ── Audio helpers ──────────────────────────────────────
  function base64ToFloat32(b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const int16 = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;
    return float32;
  }

  async function playAudioQueue() {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
    isPlayingRef.current = true;
    while (audioQueueRef.current.length > 0) {
      const chunk = audioQueueRef.current.shift();
      const buf = audioContextRef.current.createBuffer(1, chunk.length, 24000);
      buf.copyToChannel(chunk, 0);
      const src = audioContextRef.current.createBufferSource();
      src.buffer = buf;
      src.connect(audioContextRef.current.destination);
      await new Promise((resolve) => {
        src.onended = resolve;
        src.start();
      });
    }
    isPlayingRef.current = false;
  }

  // ── Microphone ─────────────────────────────────────────
  async function startListening() {
    if (!audioContextRef.current)
      audioContextRef.current = new AudioContext({ sampleRate: 16000 });

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;

    const source = audioContextRef.current.createMediaStreamSource(stream);
    const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
      const float32 = e.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++)
        int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
      const b64 = btoa(
        String.fromCharCode(...new Uint8Array(int16.buffer))
      );
      wsRef.current.send(JSON.stringify({ type: "audio", data: b64 }));
    };

    source.connect(processor);
    processor.connect(audioContextRef.current.destination);
    setIsListening(true);
  }

  function stopListening() {
    processorRef.current?.disconnect();
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    setIsListening(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
    }
  }

  // ── Text query ─────────────────────────────────────────
  function sendText(e) {
    e.preventDefault();
    if (!textInput.trim() || !wsRef.current) return;
    wsRef.current.send(
      JSON.stringify({ type: "text", content: textInput.trim() })
    );
    setMessages((prev) => [
      ...prev,
      { role: "user", content: textInput.trim(), complete: true },
    ]);
    setTextInput("");
  }

  // ── Image send ─────────────────────────────────────────
  function sendImage(file, prompt) {
    const reader = new FileReader();
    reader.onload = () => {
      const b64 = reader.result.split(",")[1];
      wsRef.current?.send(
        JSON.stringify({
          type: "image",
          data: b64,
          mime_type: file.type,
          prompt: prompt || "What do you see in this image?",
        })
      );
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: `📎 Image: ${file.name}`,
          complete: true,
          isImage: true,
          imageUrl: reader.result,
        },
      ]);
    };
    reader.readAsDataURL(file);
  }

  // ── UI ─────────────────────────────────────────────────
  const statusColor = {
    disconnected: "#ef4444",
    connecting: "#f59e0b",
    connected: "#22c55e",
    retrieving: "#8b5cf6",
  }[status];

  return (
    <main
      style={{
        maxWidth: 760,
        margin: "0 auto",
        padding: "1.5rem",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #e5e7eb",
          paddingBottom: "0.75rem",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>
            🧠 OmniRAG
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
            Voice-first Adaptive Knowledge Agent
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: statusColor,
              display: "inline-block",
            }}
          />
          <span style={{ fontSize: 13, color: "#6b7280", textTransform: "capitalize" }}>
            {status}
          </span>
          {status === "disconnected" && (
            <button
              onClick={connect}
              style={{
                marginLeft: 8,
                padding: "4px 10px",
                borderRadius: 6,
                border: "1px solid #d1d5db",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              Reconnect
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          minHeight: 400,
          maxHeight: "60vh",
        }}
      >
        {messages.map((msg, i) => (
          <ResponseStream key={i} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Controls */}
      <div
        style={{
          borderTop: "1px solid #e5e7eb",
          paddingTop: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
        }}
      >
        {/* Voice + Image buttons */}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <VoiceButton
            isListening={isListening}
            onStart={startListening}
            onStop={stopListening}
            disabled={status === "disconnected"}
          />
          <ImageUpload onImage={sendImage} disabled={status === "disconnected"} />
          <span style={{ fontSize: 12, color: "#9ca3af" }}>
            {isListening ? "Listening… (click to stop)" : "Click mic to speak"}
          </span>
        </div>

        {/* Text input */}
        <form
          onSubmit={sendText}
          style={{ display: "flex", gap: "0.5rem" }}
        >
          <input
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Or type your question here…"
            disabled={status === "disconnected"}
            style={{
              flex: 1,
              padding: "0.6rem 0.9rem",
              borderRadius: 8,
              border: "1px solid #d1d5db",
              fontSize: 14,
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={!textInput.trim() || status === "disconnected"}
            style={{
              padding: "0.6rem 1.2rem",
              borderRadius: 8,
              background: "#7c3aed",
              color: "white",
              border: "none",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: 500,
              opacity: !textInput.trim() ? 0.5 : 1,
            }}
          >
            Send
          </button>
        </form>
      </div>
    </main>
  );
}
