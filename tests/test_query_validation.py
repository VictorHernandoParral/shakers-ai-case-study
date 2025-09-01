# =============================================
# File: tests/test_query_validation.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient

def _stub_similarity_search(query_text, audience, source, min_similarity, top_k):
    # Minimal, fast stub to avoid touching the real index
    docs = ["Payments are processed weekly every Friday."]
    metas = [{"title": "057-what-is-shakers-payments", "relpath": "payments/057.md", "chunk_index": 0}]
    sims = [0.92]
    return docs, metas, sims

def _mount_client(monkeypatch):
    # Keep limiter permissive for tests
    monkeypatch.setenv("RL_MAX_REQS", "100")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")

    # Patch retrieval used by the router
    import app.routers.query as qmod
    monkeypatch.setattr(qmod, "similarity_search", _stub_similarity_search)

    from app.main import app
    return TestClient(app)

def test_rejects_empty_query(monkeypatch):
    client = _mount_client(monkeypatch)
    r = client.post("/query", json={"user_id": "u1", "query": "   "})
    assert r.status_code == 422  # Pydantic validation error

def test_rejects_too_long_query(monkeypatch):
    client = _mount_client(monkeypatch)
    long_q = "a" * 501
    r = client.post("/query", json={"user_id": "u1", "query": long_q})
    assert r.status_code == 422

def test_rejects_invalid_audience(monkeypatch):
    client = _mount_client(monkeypatch)
    r = client.post("/query", json={"user_id": "u1", "query": "Hi", "audience": "partner"})
    assert r.status_code == 422

def test_accepts_valid_payload(monkeypatch):
    client = _mount_client(monkeypatch)
    r = client.post("/query", json={"user_id": "u1", "query": "How often are payments processed?", "audience": "company"})
    # Could be 200 or 429 depending on prior calls; just ensure it's not a validation error
    assert r.status_code in (200, 429)
    if r.status_code == 200:
        data = r.json()
        assert "answer" in data and "refs" in data and "oos" in data
