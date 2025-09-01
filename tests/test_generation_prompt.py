# =============================================
# File: tests/test_generation_prompt.py
# Purpose: Validate message building + fallback path (no API key)
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import os
from app.services.generation import generate_with_llm, OOS_SENTENCE

def test_generation_fallback_without_api_key(monkeypatch):
    # Ensure we don't call the real API
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    query = "How often are payments processed?"
    # Make contents long enough (>200 chars total) and 2 items to pass evidence guard
    sources = [
        {
            "id":"1","title":"018-how-does-the-payment-system-work","url":"u",
            "content": (
                "The payment system processes invoices on a weekly cycle with transfers initiated every Friday. "
                "In practice, once an invoice is approved, it is added to the next Friday batch for bank transfer, "
                "and beneficiaries typically see funds within standard banking settlement windows depending on their bank."
            ),
        },
        {
            "id":"2","title":"012-how-can-i-start-working-with-a-freelancer","url":"u",
            "content": (
                "Once a project is accepted, you coordinate via in-app chat and set milestones. "
                "Milestones help segment work and approvals, which in turn align invoice issuance and predictable payment timing."
            ),
        },
    ]
    ans, meta = generate_with_llm(query, sources)
    assert ans  # non-empty fallback text
    assert meta["model"] == "fallback-extractive"
    assert meta["oos"] is False

def test_generation_oos_guard(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    query = "Complex question"
    sources = [{"id":"x","title":"t","url":"u","content":"Too short."}]  # not enough evidence
    ans, meta = generate_with_llm(query, sources)
    assert ans == OOS_SENTENCE
    assert meta["oos"] is True
