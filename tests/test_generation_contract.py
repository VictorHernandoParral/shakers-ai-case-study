import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_query_returns_answer_with_sources_in_scope():
    payload = {"user_id": "t_gen_1", "query": "How do payments work on Shakers?"}
    r = client.post("/query", json=payload)
    assert r.status_code == 200
    data = r.json()

    # contract
    assert isinstance(data.get("answer", ""), str)
    assert data.get("oos") is False

    # citations/sources
    sources = data.get("sources") or data.get("refs") or []
    assert isinstance(sources, list) and len(sources) >= 1
    s0 = sources[0]
    assert "title" in s0 and "url" in s0

    # safe urls
    url = s0["url"]
    assert url.startswith("kb://") or url.startswith("http")

def test_query_returns_oos_for_out_domain():
    payload = {"user_id": "t_gen_2", "query": "Who won the 2010 FIFA World Cup?"}
    r = client.post("/query", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("oos") is True
    # OOS should not cite sources
    sources = data.get("sources") or data.get("refs") or []
    assert sources == []
