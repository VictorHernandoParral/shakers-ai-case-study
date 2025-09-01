# =============================================
# File: app/utils/reranker.py
# Purpose: Reorder retrieved chunks by relevance using a cross-encoder
# =============================================
from __future__ import annotations
from typing import List, Dict
from sentence_transformers import CrossEncoder

# Load once at module import (model is small, ~100MB, fast on CPU)
_reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank(query: str, chunks: List[Dict], top_k: int = 4) -> List[Dict]:
    """
    Reorder chunks by semantic relevance to the query.

    Args:
        query: User question (English string).
        chunks: List of dicts with fields: {"id", "title", "url", "content"}.
        top_k: How many top chunks to keep.

    Returns:
        List of dicts sorted by relevance (length <= top_k).
    """
    if not chunks:
        return []

    # Prepare inputs for the cross-encoder
    pairs = [(query, ch.get("content", "")) for ch in chunks]

    # Compute scores
    scores = _reranker.predict(pairs)

    # Attach scores
    for ch, sc in zip(chunks, scores):
        ch["_score"] = float(sc)

    # Sort and select top_k
    sorted_chunks = sorted(chunks, key=lambda x: x["_score"], reverse=True)
    return sorted_chunks[:top_k]
