
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))


from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_e2e_query_then_recommend_then_metrics():
    u = "t_e2e_1"

    # 1) In-scope query -> should record a normal answer (oos False)
    r1 = client.post("/query", json={"user_id": u, "query": "Explain project workflow and milestones"})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1.get("oos") is False
    srcs1 = body1.get("sources") or body1.get("refs") or []
    assert isinstance(srcs1, list) and len(srcs1) >= 1

    # 2) Recommendations -> should return 1..3 with reason
    r2 = client.post("/recommend", json={"user_id": u, "query": "freelancers and hiring policy"})
    assert r2.status_code == 200
    recs = r2.json().get("recommendations", [])
    assert 1 <= len(recs) <= 3
    assert all("reason" in rec and len(rec["reason"]) > 10 for rec in recs)

    # 3) Metrics -> performance section must contain /query and /recommend entries
    m = client.get("/metrics")
    assert m.status_code == 200
    perf = m.json().get("performance") or m.json().get("performance")  # tolerant if wrapped
    if perf is None:
        # router may return snapshot() root, which contains "performance"
        perf = m.json()["performance"]
    endpoints = perf["endpoints"]
    assert any(k.endswith(" /query") for k in endpoints.keys())
    assert any(k.endswith(" /recommend") for k in endpoints.keys())
