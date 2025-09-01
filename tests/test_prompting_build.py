# =============================================
# File: tests/test_prompting_build.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.utils.prompting import build_messages_en, SYS_PROMPT

def test_build_messages_contains_context_and_rules():
    sources = [
        {"title":"018-how-does-the-payment-system-work","url":"https://kb/x","content":"Payments are processed weekly every Friday."},
        {"title":"012-how-can-i-start-working-with-a-freelancer","url":"https://kb/y","content":"Coordinate via in-app chat and set milestones."},
    ]
    msgs = build_messages_en("How often are payments processed?", sources)
    assert msgs[0]["role"] == "system"
    assert "ONLY the provided CONTEXT" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    u = msgs[1]["content"]
    assert "QUESTION:" in u and "CONTEXT" in u
    assert "018-how-does-the-payment-system-work" in u
    assert "Keep answers <= 6 sentences" in u
