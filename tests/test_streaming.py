# =============================================
# File: tests/test_streaming.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

def _mount_client(monkeypatch):
    # Permissive rate limit
    monkeypatch.setenv("RL_MAX_REQS", "100")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")

    # Stub retrieval & generation
    def _stub_similarity_search(query_text, audience, source, min_similarity, top_k):
        docs = ["Payments are processed weekly every Friday. This ensures predictable cash flow for freelancers."]
        metas = [{"title": "057-what-is-shakers-payments", "relpath": "payments/057.md", "chunk_index": 0}]
        sims = [0.95]
        return docs, metas, sims

    def _stub_generate_with_llm(query, sources):
        text = "Payments are processed weekly every Friday.\n\nSources: [057-what-is-shakers-payments](kb://payments/057.md)"
        meta = {"model": "fallback-extractive", "oos": False}
        return text, meta

    import app.routers.query as qmod
    monkeypatch.setattr(qmod, "similarity_search", _stub_similarity_search)
    monkeypatch.setattr(qmod, "generate_with_llm", _stub_generate_with_llm)

    from app.main import app
    return TestClient(app)

def test_sse_stream_contains_body_sources_and_done(monkeypatch):
    client = _mount_client(monkeypatch)
    r = client.get(
        "/query/stream",
        params={"user_id":"u1","query":"How often are payments processed?"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text

    # Body chunk should appear (without event label)
    assert "data: Payments are processed weekly every Friday." in body
    # Sources should be sent as a dedicated event
    assert "event: sources" in body
    assert "data: Sources: [057-what-is-shakers-payments](kb://payments/057.md)" in body
    # A meta event should be present
    assert "event: meta" in body and '"oos": false' in body
    # Stream closes with [DONE]
    assert "data: [DONE]" in body
