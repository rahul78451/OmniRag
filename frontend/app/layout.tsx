import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "OmniRAG — Adaptive Multimodal RAG Agent",
  description: "Voice-first knowledge agent powered by Gemini Live API",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <style>{`
          * { box-sizing: border-box; }
          body { margin: 0; background: #fafafa; }
          @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        `}</style>
      </head>
      <body>{children}</body>
    </html>
  );
}
