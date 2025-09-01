# =============================================
# File: app/services/rag.py
# Purpose: Retrieval -> Reranking -> Compression -> LLM Answer (English)
# =============================================
import time
from typing import Any, List, Dict

from ..utils.prompts import SYSTEM_PROMPT  # (ok if unused)
from ..utils.retrieval import RetrievalEngine
from ..utils.caching import cache_get, cache_set
from ..utils.reranker import rerank
from ..utils.compressor import compress_chunks
from .generation import generate_with_llm  # local service

retriever = RetrievalEngine()

def _try_build_chunks_from_ctx(ctx) -> List[Dict[str, str]]:
    """Best-effort adapter for whatever the retriever returns."""
    chunks: List[Dict[str, str]] = []
    sources = getattr(ctx, "sources", None)
    if not sources:
        return chunks
    for s in sources:
        chunks.append(
            {
                "id": getattr(s, "id", "") or "",
                "title": getattr(s, "title", "") or "KB",
                "url": getattr(s, "url", "") or "",
                "content": getattr(s, "content", "") or "",
            }
        )
    return chunks

def _fallback_similarity_search(query: str, k: int = 12) -> List[Dict[str, str]]:
    """Fallback path using the same retrieval that your router already uses."""
    try:
        # lazy import to avoid circulars at import time
        from app.services.retrieval import similarity_search
        docs, metas, sims = similarity_search(
            query_text=query,
            audience=None,
            source=None,
            min_similarity=0.0,
            top_k=k,
        )
    except Exception:
        return []

    chunks: List[Dict[str, str]] = []
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        title = meta.get("title") or meta.get("relpath") or meta.get("source") or "KB"
        url = meta.get("url") or (f"kb://{meta.get('relpath')}" if meta.get("relpath") else "")
        chunks.append(
            {
                "id": str(i),
                "title": title,
                "url": url,
                "content": doc or "",
            }
        )
    return chunks

async def answer_query(user_id: str, query: str) -> dict[str, Any]:
    t0 = time.perf_counter()

    cache_key = f"q::{query}"
    cached = cache_get(cache_key)
    if cached:
        cached["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return cached

    # 1) Retrieval: try engine.search first; if no usable sources, fallback to similarity_search
    raw_chunks: List[Dict[str, str]] = []
    try:
        ctx = retriever.search(query, k=12)
        raw_chunks = _try_build_chunks_from_ctx(ctx)
    except TypeError:
        # older signature without k
        try:
            ctx = retriever.search(query)
            raw_chunks = _try_build_chunks_from_ctx(ctx)
        except Exception:
            raw_chunks = []
    except Exception:
        raw_chunks = []

    if not raw_chunks:
        raw_chunks = _fallback_similarity_search(query, k=12)

    # Out-of-scope if we still have nothing
    if not raw_chunks:
        result = {
            "answer": "I don't have information on this. Please ask about platform features, payments, or freelancers.",
            "sources": [],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "oos": True,
            "model": None,
        }
        cache_set(cache_key, result)
        return result

    # 2) Rerank retrieved chunks
    top_chunks = rerank(query, raw_chunks, top_k=min(4, len(raw_chunks)))

    # 3) Compress each selected chunk
    compressed_chunks = compress_chunks(query, top_chunks, max_sentences=2)

    # 4) Generate with LLM (gpt-4o-mini)
    prompt_sources = compressed_chunks  # already dicts with {id,title,url,content}
    answer, meta = generate_with_llm(query, prompt_sources)

    # 5) Prepare response
    result_sources = [
        {"id": ch.get("id", ""), "title": ch.get("title", "KB"), "url": ch.get("url", "")}
        for ch in compressed_chunks
    ]

    result = {
        "answer": answer,
        "sources": result_sources,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "oos": bool(meta.get("oos")),
        "model": meta.get("model"),
    }
    cache_set(cache_key, result)
    return result
