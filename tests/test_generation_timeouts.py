# =============================================
# File: tests/test_generation_timeouts.py
# Purpose: Ensure timeouts/retries fall back gracefully and succeed when retry works
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pytest
from app.services import generation as gen


def test_fallback_when_all_timeouts(monkeypatch):
    # Relax evidence thresholds for this test
    monkeypatch.setenv("LLM_MIN_CHARS", "1")
    monkeypatch.setenv("LLM_MIN_ITEMS", "1")

    # Force API path (pretend we have SDK & key)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(gen, "_OPENAI_AVAILABLE", True, raising=False)

    # Simulate that _chat_completion_with_retry failed all attempts
    monkeypatch.setattr(gen, "_chat_completion_with_retry", lambda client, messages: (None, None))

    query = "How often are payments processed?"
    sources = [
        {"id":"1","title":"018","url":"https://kb/x","content":"Payments are processed weekly; transfers every Friday."},
        {"id":"2","title":"012","url":"https://kb/y","content":"Project coordination via chat and milestones."},
    ]
    ans, meta = gen.generate_with_llm(query, sources)
    assert meta["oos"] is False
    assert meta["model"] == "fallback-extractive"
    assert "Sources:" in ans  # citations ensured in fallback


def test_retry_then_success(monkeypatch):
    # Relax thresholds so 1 short source is ok
    monkeypatch.setenv("LLM_MIN_CHARS", "1")
    monkeypatch.setenv("LLM_MIN_ITEMS", "1")

    # Force API path (pretend we have SDK & key)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(gen, "_OPENAI_AVAILABLE", True, raising=False)

    # Simulate that _chat_completion_with_retry eventually succeeds
    def fake_retry_ok(client, messages):
        # Returning what the helper would give after a successful call
        return ("All good. Weekly payments every Friday. [018](https://kb/x)", "gpt-4o-mini")

    monkeypatch.setattr(gen, "_chat_completion_with_retry", fake_retry_ok)

    query = "How often are payments processed?"
    sources = [{"id":"1","title":"018","url":"https://kb/x","content":"Payments weekly; Friday transfers."}]
    ans, meta = gen.generate_with_llm(query, sources)
    assert meta["oos"] is False
    assert "gpt-4o" in (meta["model"] or "")
    # Should not be the fallback text (either inline citations or styled body)
    assert "fallback-extractive" not in str(meta.get("model"))
