"""
OmniRAG - Adaptive Multimodal RAG Agent
Main FastAPI entry point
"""

import asyncio
import os
import logging
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from gemini_live import GeminiLiveSession
from adaptive_rag import AdaptiveRAG
from ingestion import DocumentIngester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rag = None
ingester = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag, ingester
    logger.info("Initializing OmniRAG components...")
    rag = AdaptiveRAG()
    ingester = DocumentIngester(rag=rag)
    await rag.initialize()
    logger.info("OmniRAG ready!")
    yield
    logger.info("Shutting down OmniRAG...")


app = FastAPI(
    title="OmniRAG - Adaptive Multimodal RAG Agent",
    description="Voice-first adaptive knowledge agent powered by Gemini Live API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "OmniRAG", "version": "1.0.0"}


@app.websocket("/ws/live")
async def live_session(websocket: WebSocket):
    await websocket.accept()
    logger.info("New live session started")
    session = GeminiLiveSession(rag=rag, websocket=websocket)
    try:
        await session.run()
    except Exception as e:
        logger.error(f"Live session error: {e}")
    finally:
        logger.info("Live session ended")


@app.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    try:
        result = await ingester.ingest(file)
        return JSONResponse(content={
            "status": "success",
            "filename": file.filename,
            "chunks": result["chunks"],
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def text_query(request: dict):
    try:
        result = await rag.query({"query": request.get("query", "")})
        return JSONResponse(content={"answer": result, "status": "success"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")