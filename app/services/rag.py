import time
from typing import Any
from ..utils.prompts import SYSTEM_PROMPT
from ..utils.retrieval import RetrievalEngine
from ..utils.caching import cache_get, cache_set

retriever = RetrievalEngine()

async def answer_query(user_id: str, query: str) -> dict[str, Any]:
    t0 = time.perf_counter()

    cache_key = f"q::{query}"
    cached = cache_get(cache_key)
    if cached:
        cached["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return cached

    # Retrieve context
    ctx = retriever.search(query)
    oos = ctx.is_oos

    if oos:
        result = {
            "answer": "I don't have information on this. Please ask about platform features, payments, or freelancers.",
            "sources": [],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "oos": True,
        }
        cache_set(cache_key, result)
        return result

    # Generate (placeholder — plug your LLM here)
    # For the scaffold we do extractive summarization from the retrieved chunks.
    answer = retriever.generate_answer(query, ctx)

    result = {
        "answer": answer,
        "sources": [{"id": s.id, "title": s.title, "url": s.url} for s in ctx.sources],
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "oos": False,
    }
    cache_set(cache_key, result)
    return result
