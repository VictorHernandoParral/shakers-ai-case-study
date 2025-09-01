# =============================================
# File: tests/test_metrics.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.utils.metrics import reset as metrics_reset

# Stub fast retrieval + generation to avoid heavy calls
def _stub_similarity_search(query_text, audience, source, min_similarity, top_k):
    docs = ["Payments are processed weekly every Friday."]
    metas = [{"title": "057-what-is-shakers-payments", "relpath": "payments/057.md", "chunk_index": 0}]
    sims = [0.95]
    return docs, metas, sims

def _stub_generate_with_llm(query, sources):
    # Return a short answer and meta with a model name
    return ("Weekly payments. [057](kb://payments/057.md)", {"model": "fallback-extractive", "oos": False})

def _mount_client(monkeypatch):
    # Make rate limit permissive for this test
    monkeypatch.setenv("RL_MAX_REQS", "100")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")
    metrics_reset()

    import app.routers.query as qmod
    monkeypatch.setattr(qmod, "similarity_search", _stub_similarity_search)
    monkeypatch.setattr(qmod, "generate_with_llm", _stub_generate_with_llm)

    from app.main import app
    return TestClient(app)

def test_metrics_counts_and_models(monkeypatch):
    client = _mount_client(monkeypatch)
    # Two successful requests
    for _ in range(2):
        r = client.post("/query", json={"user_id": "u1", "query": "How often are payments processed?"})
        assert r.status_code in (200, 429)

    m = client.get("/metrics").json()
    assert m["counters"]["requests_total"] >= 2
    assert m["model_usage"].get("fallback-extractive", 0) >= 2
    # histogram consistency: sum of buckets equals requests_total
    hist_sum = sum(m["latency_ms"]["counts"])
    assert hist_sum == m["counters"]["requests_total"]

def test_rate_limit_is_counted(monkeypatch):
    client = _mount_client(monkeypatch)
    # Tight limiter
    monkeypatch.setenv("RL_MAX_REQS", "1")
    # First call allowed
    _ = client.post("/query", json={"user_id": "rltest", "query": "Ping?"})
    # Second call should hit 429
    _ = client.post("/query", json={"user_id": "rltest", "query": "Ping again?"})
    m = client.get("/metrics").json()
    assert m["counters"]["rate_limit_hits_total"] >= 1
