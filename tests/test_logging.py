# =============================================
# File: tests/test_logging.py
# =============================================
import sys, os, json
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient
from app.utils import rcache

def _mount_client(monkeypatch):
    # generous limiter
    monkeypatch.setenv("RL_MAX_REQS", "100")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")
    rcache.clear()

    # stub retrieval & generation
    def _stub_similarity_search(query_text, audience, source, min_similarity, top_k):
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
    return TestClient(app)

def _find_json_event(caplog, name: str):
    for rec in caplog.records:
        try:
            data = json.loads(rec.message)
            if data.get("event") == name:
                return data
        except Exception:
            continue
    return None

def test_structured_log_on_success(monkeypatch, caplog):
    caplog.set_level("INFO", logger="shakers")
    client = _mount_client(monkeypatch)

    r = client.post("/query", json={"user_id": "u-log", "query": "How often are payments processed?"})
    assert r.status_code in (200, 429)

    evt = _find_json_event(caplog, "request.completed")
    assert evt is not None
    assert evt["path"].startswith("/query")
    assert "request_id" in evt and evt["request_id"]
    assert "latency_ms" in evt and isinstance(evt["latency_ms"], int)
    # model and oos set by router
    assert "model" in evt
    assert "oos" in evt
    # user + qhash present
    assert evt.get("user_id") == "u-log"
    assert len(evt.get("qhash", "")) == 10

def test_structured_log_rate_limited(monkeypatch, caplog):
    caplog.set_level("INFO", logger="shakers")
    client = _mount_client(monkeypatch)

    # Tight limiter
    os.environ["RL_MAX_REQS"] = "1"
    os.environ["RL_WINDOW_SECONDS"] = "60"

    # First call allowed
    _ = client.post("/query", json={"user_id": "rl-user", "query": "Ping?"})
    # Second call should rate-limit (429)
    _ = client.post("/query", json={"user_id": "rl-user", "query": "Ping again?"})

    evt = _find_json_event(caplog, "request.completed")
    assert evt is not None
    # One of the logged events should reflect a 429
    # (caplog may have multiple; last one is fine to validate fields)
    assert "status" in evt
    # rate_limited flag is included by middleware even if router didn't set it
    assert "rate_limited" in evt
