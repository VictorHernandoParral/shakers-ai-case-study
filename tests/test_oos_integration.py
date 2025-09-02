import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

def test_oos_for_clearly_out_domain():
    payload = {"user_id": "u1", "query": "Who won the 2010 FIFA World Cup?"}
    r = client.post("/query", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("oos") is True
    ans = data.get("answer", "")
    assert (
        "I don't have information on this" in ans
        or "I couldn't find a confident answer in the knowledge base" in ans
    )
    sources = data.get("sources")
    if sources is None:
        sources = data.get("refs")  # tolera la clave antigua
    assert sources == []

def test_in_scope_not_oos():
    payload = {"user_id": "u1", "query": "How do payments work on Shakers?"}
    r = client.post("/query", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("oos") is False
    assert isinstance(data.get("answer", ""), str) and len(data["answer"]) > 0
    assert isinstance(data.get("sources", []), list)
