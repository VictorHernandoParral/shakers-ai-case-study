# =============================================
# File: tests/test_rag_integration.py
# Purpose: End-to-end test for answer_query with rerank+compress+LLM fallback
# =============================================
import sys, os
import types
import pytest

# Ensure project root on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from dataclasses import dataclass

@pytest.mark.asyncio
async def test_answer_query_integration(monkeypatch):
    # Import here to access the real module objects
    from app.services import rag

    # 1) Forzar que NO se use la API de OpenAI => fallback
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # 2) Stub para la respuesta de búsqueda (ctx)
    @dataclass
    class SourceStub:
        id: str
        title: str
        url: str
        content: str

    class CtxStub:
        def __init__(self, sources, is_oos=False):
            self.sources = sources
            self.is_oos = is_oos

    def fake_search(query, k=12):
        # Dos fuentes sintéticas, una muy relevante
        s1 = SourceStub(
            id="1",
            title="018-how-does-the-payment-system-work",
            url="https://kb/shakers_faq/company/018",
            content=(
                "The payment system processes invoices on a weekly cycle with transfers initiated every Friday. "
                "Funds usually settle within standard banking windows depending on the receiving bank."
            ),
        )
        s2 = SourceStub(
            id="2",
            title="012-how-can-i-start-working-with-a-freelancer",
            url="https://kb/shakers_faq/company/012",
            content=(
                "Once a project is accepted, coordination happens via the in-app chat and milestones are defined."
            ),
        )
        return CtxStub([s1, s2], is_oos=False)

    # 3) Monkeypatch del search real
    monkeypatch.setattr(rag.retriever, "search", fake_search)

    # 4) Evitar cargar modelos pesados: neutralizamos rerank/compress
    def fake_rerank(query, chunks, top_k=4):
        # Devolvemos tal cual la lista original (ya “suficientemente buena” para el test)
        return chunks[:top_k]

    def fake_compress_chunks(query, chunks, max_sentences=2):
        # Devolvemos los mismos contenidos (sin compresión) para simplificar el test
        return chunks

    monkeypatch.setattr(rag, "rerank", fake_rerank)
    monkeypatch.setattr(rag, "compress_chunks", fake_compress_chunks)

    # 5) Ejecutar la función asíncrona
    result = await rag.answer_query(user_id="u1", query="How often are payments processed?")

    # 6) Asserts
    assert isinstance(result, dict)
    assert result["oos"] is False
    assert "answer" in result and result["answer"]
    assert "sources" in result and len(result["sources"]) >= 1
    # En fallback, el "model" debería ser 'fallback-extractive'
    assert result.get("model") in (None, "fallback-extractive") or "gpt" in str(result.get("model")).lower()
    # Debe contener alguna pista del texto relevante
    assert "weekly" in result["answer"].lower() or "friday" in result["answer"].lower()
