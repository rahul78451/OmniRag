"""
Adaptive RAG Engine
"""

import os
import json
import logging
import hashlib
from typing import Optional
from google import genai
from google.genai import types as genai_types, types
from google.cloud import firestore, storage

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ.get("PROJECT_ID", "omnirag-local")
LOCATION = os.environ.get("LOCATION", "us-central1")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "omnirag-local-docs")
EMBEDDING_MODEL = "text-embedding-004"
GENERATION_MODEL = "gemini-2.0-flash-lite"


def make_client():
    import os
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return genai.Client(api_key=api_key)


class AdaptiveRAG:
    def __init__(self):
        self.client = make_client()
        self.db = None
        self.storage_client = None
        self.bucket = None
        self.documents = []

    async def initialize(self):
        try:
            self.db = firestore.AsyncClient(project=PROJECT_ID)
            self.storage_client = storage.Client(project=PROJECT_ID)
            try:
                self.bucket = self.storage_client.bucket(GCS_BUCKET)
                if not self.bucket.exists():
                    self.bucket = self.storage_client.create_bucket(
                        GCS_BUCKET, location="US"
                    )
            except Exception as e:
                logger.warning(f"GCS bucket setup warning: {e}")
            logger.info("Google Cloud clients initialized")
        except Exception as e:
            logger.warning(f"Cloud init warning (using local fallback): {e}")

    async def query(self, args: dict) -> str:
        query = args.get("query", "")
        complexity = args.get("complexity", "medium")
        image_context = args.get("image_context")

        logger.info(f"Query: '{query}' | complexity={complexity}")

        if complexity == "medium":
            complexity = self._detect_complexity(query)

        if not self.documents:
            return await self._direct_answer(query, image_context)

        if complexity == "simple":
            return await self._direct_answer(query, image_context)
        elif complexity == "complex":
            return await self._multi_hop_answer(query, image_context)
        else:
            return await self._single_hop_answer(query, image_context)

    async def _direct_answer(self, query: str, image_context: Optional[str] = None) -> str:
        prompt = query
        if image_context:
            prompt = f"[Image context: {image_context}]\n{query}"
        response = self.client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
        )
        return response.text

    async def _single_hop_answer(self, query: str, image_context: Optional[str] = None) -> str:
        docs = await self._retrieve(query, top_k=5)
        if not docs:
            return await self._direct_answer(query, image_context)
        context = self._format_context(docs)
        prompt = f"""Answer using the context below. Cite the source document name.

Context:
{context}

Question: {query}

Answer:"""
        response = self.client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
        )
        return response.text

    async def _multi_hop_answer(self, query: str, image_context: Optional[str] = None) -> str:
        decompose_prompt = f"""Break this into 2-3 simpler sub-questions.
Return ONLY a JSON array of strings.
Question: {query}"""
        decomp = self.client.models.generate_content(
            model=GENERATION_MODEL,
            contents=decompose_prompt,
        )
        try:
            raw = decomp.text.strip().strip("```json").strip("```").strip()
            sub_questions = json.loads(raw)
        except Exception:
            return await self._single_hop_answer(query, image_context)

        all_docs = []
        for sub_q in sub_questions[:3]:
            docs = await self._retrieve(sub_q, top_k=3)
            all_docs.extend(docs)

        seen = set()
        unique_docs = []
        for doc in all_docs:
            if doc["id"] not in seen:
                seen.add(doc["id"])
                unique_docs.append(doc)

        if not unique_docs:
            return await self._direct_answer(query, image_context)

        context = self._format_context(unique_docs)
        prompt = f"""Answer using the context. Cite each source.

Context:
{context}

Question: {query}

Answer:"""
        response = self.client.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
        )
        return response.text

    async def _retrieve(self, query: str, top_k: int = 5) -> list:
        if not self.documents:
            return []
        query_emb = self._embed_text(query)
        scored = []
        for doc in self.documents:
            score = self._cosine_similarity(query_emb, doc["embedding"])
            scored.append({**doc, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def _embed_text(self, text: str) -> list:
        response = self.client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=text,
        )
        return response.embeddings[0].values

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x ** 2 for x in a) ** 0.5
        mag_b = sum(x ** 2 for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def _format_context(docs: list) -> str:
        parts = []
        for i, doc in enumerate(docs, 1):
            source = doc.get("metadata", {}).get("source", f"Document {i}")
            score = doc.get("score", 0)
            parts.append(f"[Source {i}: {source} (relevance: {score:.2f})]\n{doc['text']}")
        return "\n\n".join(parts)

    def _detect_complexity(self, query: str) -> str:
        q = query.lower()
        word_count = len(q.split())
        complex_signals = ["compare", "difference", "how does", "why", "explain",
                           "analyze", "relationship", "impact", "cause", "multiple"]
        simple_signals = ["what is", "who is", "when", "where", "define", "list"]
        if any(s in q for s in complex_signals) or word_count > 20:
            return "complex"
        if any(s in q for s in simple_signals) or word_count < 8:
            return "simple"
        return "medium"

    async def add_document(self, text: str, metadata: dict) -> int:
        doc_id = hashlib.md5(text.encode()).hexdigest()[:12]
        embedding = self._embed_text(text[:2000])
        self.documents.append({
            "id": doc_id,
            "text": text,
            "embedding": embedding,
            "metadata": metadata,
        })
        return len(self.documents)

    async def clear(self):
        self.documents.clear()
        logger.info("Knowledge base cleared")