"""
Document ingestion pipeline
Handles PDF, image, plain-text ingestion with chunking and embedding
"""

import io
import os
import logging
from typing import Optional
from fastapi import UploadFile

logger = logging.getLogger(__name__)

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 100    # overlap between chunks


class DocumentIngester:
    """Ingests documents into the AdaptiveRAG knowledge base."""

    def __init__(self, rag):
        self.rag = rag

    async def ingest(self, file: UploadFile) -> dict:
        """Auto-detect file type and ingest."""
        content = await file.read()
        filename = file.filename or "unknown"
        mime = file.content_type or ""

        if mime == "application/pdf" or filename.endswith(".pdf"):
            text = self._extract_pdf(content)
        elif mime.startswith("image/"):
            text = await self._extract_image(content, mime, filename)
        else:
            # Plain text / markdown / code
            text = content.decode("utf-8", errors="replace")

        chunks = self._chunk_text(text)
        count = 0
        for i, chunk in enumerate(chunks):
            await self.rag.add_document(
                text=chunk,
                metadata={
                    "source": filename,
                    "chunk": i,
                    "total_chunks": len(chunks),
                }
            )
            count += 1

        logger.info(f"Ingested {filename}: {count} chunks")
        return {"chunks": count, "filename": filename}

    # ─────────────────────────────────────────────
    # Extractors
    # ─────────────────────────────────────────────

    def _extract_pdf(self, content: bytes) -> str:
        """Extract text from PDF using PyMuPDF if available, else fallback."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(stream=content, filetype="pdf")
            pages = [page.get_text() for page in doc]
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("PyMuPDF not installed — using raw text extraction")
            return content.decode("utf-8", errors="replace")

    async def _extract_image(self, content: bytes, mime: str, filename: str) -> str:
        """Use Gemini Vision to extract text/description from an image."""
        import base64
        from google import genai
        from google.genai import types

        client = genai.Client()
        image_b64 = base64.b64encode(content).decode()

        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=base64.b64decode(image_b64),
                                mime_type=mime
                            )
                        ),
                        types.Part(
                            text=(
                                "Extract and describe all text, data, diagrams, "
                                "and important visual information from this image. "
                                "Be comprehensive — this will be used for retrieval."
                            )
                        )
                    ]
                )
            ],
        )
        extracted = response.text
        return f"[Image: {filename}]\n{extracted}"

    # ─────────────────────────────────────────────
    # Chunking
    # ─────────────────────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        text = text.strip()
        if not text:
            return []

        # First try paragraph-based splitting
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) < CHUNK_SIZE:
                current += ("\n\n" if current else "") + para
            else:
                if current:
                    chunks.append(current)
                    # Keep overlap
                    overlap_start = max(0, len(current) - CHUNK_OVERLAP)
                    current = current[overlap_start:] + "\n\n" + para
                else:
                    # Single paragraph larger than chunk size
                    for i in range(0, len(para), CHUNK_SIZE - CHUNK_OVERLAP):
                        chunks.append(para[i: i + CHUNK_SIZE])
                    current = ""

        if current:
            chunks.append(current)

        return [c for c in chunks if len(c.strip()) > 50]
