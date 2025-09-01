# =============================================
# File: tests/test_reranker.py
# Purpose: Validate reranking logic (with path fix)
# =============================================
import sys, os
import pytest

# Ensure project root is on sys.path so "app" can be imported
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.utils.reranker import rerank

def test_rerank_returns_sorted_chunks():
    query = "How does payment work?"

    chunks = [
        {
            "id": "1",
            "title": "Payments",
            "url": "https://kb/payments",
            "content": "Payments are processed weekly via bank transfer.",
        },
        {
            "id": "2",
            "title": "Profile",
            "url": "https://kb/profile",
            "content": "You can edit your profile settings here.",
        },
    ]

    ranked = rerank(query, chunks, top_k=1)

    # Assertions
    assert isinstance(ranked, list)
    assert len(ranked) == 1
    assert ranked[0]["title"] == "Payments"  # "Payments" should be top
    assert "_score" in ranked[0]  # reranker attaches score

def test_rerank_handles_empty_input():
    query = "What is Shakers?"
    chunks = []
    ranked = rerank(query, chunks, top_k=3)
    assert ranked == []
