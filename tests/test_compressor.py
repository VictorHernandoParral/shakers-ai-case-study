# =============================================
# File: tests/test_compressor.py
# Purpose: Validate context compression (path-safe)
# =============================================
import sys, os
import pytest

# Ensure project root on sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.utils.compressor import compress_chunk, split_sentences

def test_compress_chunk_basic():
    query = "How does the payment system work?"

    # Two-sentence chunk: one highly relevant to payments, one generic
    chunk = {
        "id": "x1",
        "title": "018-how-does-the-payment-system-work",
        "url": "https://kb/shakers_faq/company/018",
        "content": (
            "The payment system processes invoices on a weekly cycle with transfers initiated every Friday. "
            "Users can customize some profile preferences in their account settings."
        ),
    }

    compressed = compress_chunk(query, chunk, max_sentences=1)

    # It should return exactly one sentence
    sents = split_sentences(compressed["content"])
    assert len(sents) == 1

    # The kept sentence should be the payment-related one
    assert "payment system" in sents[0].lower() or "invoices" in sents[0].lower() or "transfers" in sents[0].lower()

def test_compress_chunk_handles_empty_or_single_sentence():
    query = "General question"

    # Empty content
    empty_chunk = {"id": "e1", "title": "empty", "url": "u", "content": ""}
    c1 = compress_chunk(query, empty_chunk, max_sentences=2)
    assert c1["content"] == ""

    # Single sentence remains as-is
    single_chunk = {"id": "s1", "title": "single", "url": "u",
                    "content": "Projects are reviewed within 48 hours."}
    c2 = compress_chunk(query, single_chunk, max_sentences=2)
    assert c2["content"] == "Projects are reviewed within 48 hours."
