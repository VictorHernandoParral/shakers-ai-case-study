import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_metrics_snapshot_moves():
    # Golpea /recommend y /query para generar tráfico
    r1 = client.post("/recommend", json={"user_id": "u99", "query": "payments and invoices"})
    assert r1.status_code == 200

    r2 = client.post("/query", json={"user_id": "u99", "query": "How do payments work on Shakers?"})
    assert r2.status_code == 200

    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.json()

    assert "performance" in body
    perf = body["performance"]
    assert "endpoints" in perf and isinstance(perf["endpoints"], dict)
    eps = perf["endpoints"]
    # Debiera haber al menos entradas para /recommend y /query
    assert any(k.endswith(" /recommend") for k in eps.keys()) or any(k.endswith(" /recommend") for k in eps.keys())
    assert any(k.endswith(" /query") for k in eps.keys())

    # Cada entrada tiene count y latencias
    for k, v in eps.items():
        assert "count" in v
        assert "avg_latency_ms" in v
        assert "p95_latency_ms" in v
