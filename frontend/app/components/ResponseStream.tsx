"use client";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  complete?: boolean;
  isImage?: boolean;
  imageUrl?: string;
}

export default function ResponseStream({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div
        style={{
          textAlign: "center",
          fontSize: 12,
          color: "#8b5cf6",
          padding: "4px 0",
        }}
      >
        🔍 {message.content}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
      }}
    >
      <div
        style={{
          maxWidth: "80%",
          padding: "0.7rem 1rem",
          borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
          background: isUser ? "#7c3aed" : "#f3f4f6",
          color: isUser ? "white" : "#111827",
          fontSize: 14,
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {message.isImage && message.imageUrl && (
          <img
            src={message.imageUrl}
            alt="uploaded"
            style={{
              maxWidth: "100%",
              maxHeight: 200,
              borderRadius: 8,
              marginBottom: "0.4rem",
              display: "block",
            }}
          />
        )}
        {message.content}
        {!message.complete && message.role === "assistant" && (
          <span
            style={{
              display: "inline-block",
              width: 8,
              height: 14,
              background: "#6b7280",
              marginLeft: 3,
              borderRadius: 2,
              animation: "blink 1s step-end infinite",
            }}
          />
        )}
      </div>
    </div>
  );
}
