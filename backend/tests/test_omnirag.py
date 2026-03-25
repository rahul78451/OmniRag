"""
OmniRAG backend tests
Run: pytest backend/tests/ -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── AdaptiveRAG unit tests ────────────────────────────────
class TestComplexityDetection:
    def setup_method(self):
        from adaptive_rag import AdaptiveRAG
        self.rag = AdaptiveRAG()

    def test_simple_query(self):
        assert self.rag._detect_complexity("what is RAG?") == "simple"

    def test_simple_query_list(self):
        assert self.rag._detect_complexity("list the features") == "simple"

    def test_medium_query(self):
        result = self.rag._detect_complexity("how does vector search work in RAG systems?")
        assert result in ("medium", "complex")

    def test_complex_query(self):
        result = self.rag._detect_complexity(
            "compare and analyze the difference between multi-hop and single-hop RAG retrieval strategies"
        )
        assert result == "complex"

    def test_complex_signal_words(self):
        assert self.rag._detect_complexity("explain the relationship between embeddings and semantic search") == "complex"


class TestChunking:
    def setup_method(self):
        from ingestion import DocumentIngester
        self.ingester = DocumentIngester(rag=None)

    def test_empty_text(self):
        assert self.ingester._chunk_text("") == []

    def test_short_text_single_chunk(self):
        text = "This is a short document about AI."
        chunks = self.ingester._chunk_text(text)
        assert len(chunks) == 1
        assert "AI" in chunks[0]

    def test_long_text_multiple_chunks(self):
        # Create text longer than CHUNK_SIZE
        text = ("This is a paragraph about machine learning. " * 30 + "\n\n") * 5
        chunks = self.ingester._chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_not_empty(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three about NLP."
        chunks = self.ingester._chunk_text(text)
        assert all(len(c.strip()) > 0 for c in chunks)


class TestCosineSimilarity:
    def setup_method(self):
        from adaptive_rag import AdaptiveRAG
        self.rag = AdaptiveRAG()

    def test_identical_vectors(self):
        v = [1.0, 0.5, 0.3]
        score = self.rag._cosine_similarity(v, v)
        assert abs(score - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        score = self.rag._cosine_similarity(a, b)
        assert abs(score) < 1e-6

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 0.5]
        score = self.rag._cosine_similarity(a, b)
        assert score == 0.0

    def test_similar_vectors(self):
        a = [0.9, 0.1]
        b = [0.8, 0.2]
        score = self.rag._cosine_similarity(a, b)
        assert score > 0.95


class TestContextFormatting:
    def setup_method(self):
        from adaptive_rag import AdaptiveRAG
        self.rag = AdaptiveRAG()

    def test_format_context_includes_source(self):
        docs = [
            {"id": "1", "text": "Some text about AI.", "score": 0.9,
             "metadata": {"source": "ai_doc.pdf"}},
        ]
        ctx = self.rag._format_context(docs)
        assert "ai_doc.pdf" in ctx
        assert "Some text about AI." in ctx

    def test_format_context_multiple_docs(self):
        docs = [
            {"id": "1", "text": "Doc one content.", "score": 0.9,
             "metadata": {"source": "doc1.pdf"}},
            {"id": "2", "text": "Doc two content.", "score": 0.75,
             "metadata": {"source": "doc2.pdf"}},
        ]
        ctx = self.rag._format_context(docs)
        assert "Source 1" in ctx
        assert "Source 2" in ctx
        assert "doc1.pdf" in ctx
        assert "doc2.pdf" in ctx


# ── HTTP endpoint tests (no real GCP needed) ─────────────
@pytest.mark.asyncio
async def test_health_endpoint():
    from fastapi.testclient import TestClient
    import os
    os.environ["TESTING"] = "true"

    # Patch initialize to no-op
    from unittest.mock import AsyncMock, patch
    with patch("adaptive_rag.AdaptiveRAG.initialize", new_callable=AsyncMock):
        from main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
