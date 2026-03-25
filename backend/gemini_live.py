"""
Gemini Live API session handler - Final working version
"""

import asyncio
import json
import base64
import logging
import os
from fastapi import WebSocket
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "You are OmniRAG, a helpful knowledge agent. Answer questions clearly and concisely."

# Correct model confirmed working with free API key
MODEL = "gemini-2.5-flash-preview-native-audio-dialog"


class GeminiLiveSession:
    def __init__(self, rag, websocket: WebSocket):
        self.rag = rag
        self.ws = websocket
        self.session_active = True
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=api_key)

    async def run(self):
        config = {
            "response_modalities": ["TEXT"],
            "system_instruction": SYSTEM_PROMPT,
        }
        try:
            async with self.client.aio.live.connect(
                model=MODEL,
                config=config,
            ) as session:
                logger.info("Gemini Live connected successfully!")
                await self.ws.send_json({
                    "type": "status",
                    "content": "connected",
                    "message": "OmniRAG ready! Ask me anything."
                })
                await asyncio.gather(
                    self._recv(session),
                    self._send(session),
                )
        except Exception as e:
            logger.error(f"Session error: {e}")
            # Fallback — use regular Gemini instead of Live API
            await self._fallback_mode()

    async def _fallback_mode(self):
        """Fallback: use regular generate_content if Live API fails."""
        logger.info("Using fallback text mode")
        await self.ws.send_json({
            "type": "status",
            "content": "connected",
            "message": "OmniRAG ready (text mode)! Ask me anything."
        })
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)
        try:
            async for msg in self.ws.iter_text():
                data = json.loads(msg)
                if data.get("type") == "text":
                    query = data["content"]
                    await self.ws.send_json({
                        "type": "retrieving",
                        "query": query
                    })
                    # Use adaptive RAG
                    result = await self.rag.query({"query": query})
                    await self.ws.send_json({
                        "type": "text",
                        "content": result
                    })
                    await self.ws.send_json({"type": "turn_complete"})
                elif data.get("type") == "ping":
                    await self.ws.send_json({"type": "pong"})
        except Exception as e:
            logger.error(f"Fallback error: {e}")

    async def _recv(self, session):
        try:
            async for msg in self.ws.iter_text():
                if not self.session_active:
                    break
                data = json.loads(msg)
                t = data.get("type")

                if t == "text":
                    await session.send_client_content(
                        turns={"parts": [{"text": data["content"]}]},
                        turn_complete=True,
                    )
                elif t == "audio":
                    raw = base64.b64decode(data["data"])
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=raw,
                            mime_type="audio/pcm;rate=16000"
                        )
                    )
                elif t == "ping":
                    await self.ws.send_json({"type": "pong"})
        except Exception as e:
            logger.error(f"Recv error: {e}")
            self.session_active = False

    async def _send(self, session):
        try:
            async for resp in session.receive():
                if not self.session_active:
                    break
                if resp.text:
                    await self.ws.send_json({
                        "type": "text",
                        "content": resp.text
                    })
                if resp.server_content and resp.server_content.turn_complete:
                    await self.ws.send_json({"type": "turn_complete"})
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.session_active = False