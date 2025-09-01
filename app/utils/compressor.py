# =============================================
# File: app/utils/compressor.py
# Purpose: Compress chunks to most relevant sentences
# =============================================
from __future__ import annotations
from typing import List, Dict
import re
from sentence_transformers import SentenceTransformer, util

# Small, fast English model for embeddings
_model = SentenceTransformer("all-MiniLM-L6-v2")

def split_sentences(text: str) -> List[str]:
    """Very naive sentence splitter (can improve later)."""
    sentences = re.split(r'(?<=[.!?])\\s+', text.strip())
    return [s for s in sentences if s]

def compress_chunk(query: str, chunk: Dict, max_sentences: int = 2) -> Dict:
    """
    Returns a compressed chunk with only the most relevant sentences.
    """
    sentences = split_sentences(chunk.get("content", ""))
    if not sentences:
        return chunk

    # Encode query and sentences
    query_emb = _model.encode(query, convert_to_tensor=True)
    sent_embs = _model.encode(sentences, convert_to_tensor=True)

    # Compute cosine similarities
    scores = util.cos_sim(query_emb, sent_embs)[0]

    # Rank sentences
    scored = sorted(zip(sentences, scores.tolist()), key=lambda x: x[1], reverse=True)
    top_sentences = [s for s, _ in scored[:max_sentences]]

    compressed_content = " ".join(top_sentences)
    return {
        **chunk,
        "content": compressed_content,
    }

def compress_chunks(query: str, chunks: List[Dict], max_sentences: int = 2) -> List[Dict]:
    return [compress_chunk(query, ch, max_sentences=max_sentences) for ch in chunks]
