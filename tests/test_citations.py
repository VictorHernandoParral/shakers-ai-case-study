# =============================================
# File: tests/test_citations.py
# =============================================
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.utils.citations import ensure_citations

def test_appends_sources_when_missing():
    ans = "Payments are processed weekly."
    sources = [{"title":"018-how-does-the-payment-system-work","url":"https://kb/x"}]
    out = ensure_citations(ans, sources)
    assert "Sources:" in out
    assert "[018-how-does-the-payment-system-work](https://kb/x)" in out

def test_respects_existing_citations():
    ans = "Payments are processed weekly. [018](https://kb/x)"
    sources = [{"title":"018","url":"https://kb/x"}]
    out = ensure_citations(ans, sources)
    assert out == ans
