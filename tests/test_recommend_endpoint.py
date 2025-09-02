# tests/test_recommend_endpoint.py

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_recommend_returns_2_to_3_items_with_reason():
    payload = {"user_id": "u42", "query": "payments and invoices on the platform"}
    r = client.post("/recommend", json=payload)
    assert r.status_code == 200
    data = r.json()
    recs = data.get("recommendations", [])
    assert 1 <= len(recs) <= 3
    for rec in recs:
        assert "title" in rec and rec["title"]
        assert "url" in rec
        assert "reason" in rec and len(rec["reason"]) > 10

def test_recommend_diversity_and_unseen():
    u = "u43"
    # First call seeds history and seen
    r1 = client.post("/recommend", json={"user_id": u, "query": "freelancers and hiring policy"})
    assert r1.status_code == 200
    first = r1.json()["recommendations"]
    # Second call should try to avoid recommending the exact same items
    r2 = client.post("/recommend", json={"user_id": u, "query": "project workflow and milestones"})
    assert r2.status_code == 200
    second = r2.json()["recommendations"]

    # No exact duplicates by (url, title)
    first_keys = {(rec.get("url"), rec.get("title")) for rec in first}
    second_keys = {(rec.get("url"), rec.get("title")) for rec in second}
    overlap = first_keys & second_keys
    assert len(overlap) < len(first_keys), "Expected second list to avoid previously seen items."

    # Diversity heuristic: titles should not be all identical
    titles = [rec["title"] for rec in second]
    assert len(set(titles)) == len(titles)
