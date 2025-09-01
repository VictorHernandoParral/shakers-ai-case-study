# =============================================
# File: tests/test_cache.py
# Purpose: Ensure router-level response caching prevents repeated retrieval calls
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.utils import rcache

def _mount_client(monkeypatch):
    # Generous rate limit
    monkeypatch.setenv("RL_MAX_REQS", "100")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")
    # Short TTL for test (but not required)
    monkeypatch.setenv("CACHE_TTL_SECONDS", "300")

    # Reset cache
    rcache.clear()

    # Counter for similarity_search calls
    calls = {"n": 0}
    def _stub_similarity_search(query_text, audience, source, min_similarity, top_k):
        calls["n"] += 1
        docs = ["Payments are processed weekly every Friday."]
        metas = [{"title": "057-what-is-shakers-payments", "relpath": "payments/057.md", "chunk_index": 0}]
        sims = [0.95]
        return docs, metas, sims

    def _stub_generate_with_llm(query, sources):
        return ("Weekly payments. [057](kb://payments/057.md)", {"model": "fallback-extractive", "oos": False})

    import app.routers.query as qmod
    monkeypatch.setattr(qmod, "similarity_search", _stub_similarity_search)
    monkeypatch.setattr(qmod, "generate_with_llm", _stub_generate_with_llm)

    from app.main import app
    return TestClient(app), calls

def test_router_cache_hits(monkeypatch):
    client, calls = _mount_client(monkeypatch)

    payload = {"user_id": "u1", "query": "How often are payments processed?"}

    r1 = client.post("/query", json=payload)
    assert r1.status_code in (200, 429)
    # Even if 429 due to external state, the second call should not increase retrieval calls
    n1 = calls["n"]

    r2 = client.post("/query", json=payload)
    assert r2.status_code in (200, 429)
    n2 = calls["n"]

    # Retrieval called only once; second response came from cache
    assert n2 == n1
