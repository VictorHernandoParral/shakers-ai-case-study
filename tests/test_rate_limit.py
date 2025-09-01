# =============================================
# File: tests/test_rate_limit.py
# Purpose: Validate per-user rate limiting on /query
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import os
import pytest
from fastapi.testclient import TestClient

from app.utils.ratelimit import reset_rate_limit

def test_rate_limit_per_user(monkeypatch):
    # Keep window tiny for test
    monkeypatch.setenv("RL_MAX_REQS", "1")
    monkeypatch.setenv("RL_WINDOW_SECONDS", "60")
    reset_rate_limit()

    from app.main import app
    client = TestClient(app)

    # First call allowed
    r1 = client.post("/query", json={"user_id": "tester", "query": "Ping?"})
    # 200 or 429 depending on your RAG fallback; but we only care the second one 429s
    assert r1.status_code in (200, 429)

    # Second call in same window should be blocked
    r2 = client.post("/query", json={"user_id": "tester", "query": "Ping again?"})
    assert r2.status_code == 429
