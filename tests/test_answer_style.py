# =============================================
# File: tests/test_answer_style.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.utils.answer_style import enforce_style

def test_truncates_to_max_sentences_keeps_sources():
    body = "One. Two. Three. Four. Five. Six. Seven. Eight."
    ans = body + "\n\nSources: [Doc](http://example.com)"
    out = enforce_style(ans, max_sentences=6)
    assert "Seven" not in out and "Eight" not in out
    assert "Sources:" in out
    assert out.endswith("(http://example.com)")

def test_bulletizes_semicolon_list():
    body = "Alpha item; Beta item; Gamma item; Delta item"
    out = enforce_style(body, max_sentences=6)
    # Should become bullets
    assert out.strip().startswith("- ")
    assert "Alpha item" in out and "Delta item" in out
