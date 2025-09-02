# app/services/recommender.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from math import inf
from app.services.profiles import PROFILE_STORE
   
from app.services.retrieval import similarity_search
from loguru import logger
import os
import glob

def _kb_file_candidates(k: int = 20) -> List[Dict[str, Any]]:
    """
    Fallback: scan the local KB and build simple candidates when similarity_search returns nothing.
    Looks for .md and .txt under app/data/kb/**.
    """
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "kb")
    paths = sorted(
        glob.glob(os.path.join(base, "**", "*.md"), recursive=True) +
        glob.glob(os.path.join(base, "**", "*.txt"), recursive=True)
    )
    cands: List[Dict[str, Any]] = []
    for i, p in enumerate(paths[: max(3*k, 50)]):  # oversample a bit for diversity, cap
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            rel = os.path.relpath(p, base).replace("\\", "/")
            title = os.path.splitext(os.path.basename(p))[0].replace("_", " ").title()
            url = f"kb://{rel}"
            cands.append({
                "id": f"kbfile-{i}",
                "title": title or "KB",
                "url": url,
                "content": text[:2000],  # small preview is enough
                # No similarity here; MMR falls back to a flat prior (0.5)
            })
        except Exception:
            continue
    return cands


def _candidateize(query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Get candidate resources for recommendation using the fallback similarity_search.
    If empty, fall back to scanning KB files so we always have something to recommend.
    """
    try:
        chunks = similarity_search(query, k=k) or []
    except Exception:
        chunks = []

    if not chunks:
        # NEW: file-based fallback to avoid returning 0 recommendations
        chunks = _kb_file_candidates(k=k)

    # dedupe by (url or id)
    uniq = {}
    for c in chunks:
        key = c.get("url") or c.get("id")
        if key and key not in uniq:
            uniq[key] = c
    return list(uniq.values())

def _mmr_select(cands: List[Dict[str, Any]], k: int = 3, lam: float = 0.7) -> List[Dict[str, Any]]:
    """
    Simple MMR diversification using 'similarity' if present, else a flat prior (0.5).
    Redundancy approximated via Jaccard over title tokens.
    """
    def sim(c: Dict[str, Any]) -> float:
        try:
            return float(c.get("similarity", 0.5))
        except Exception:
            return 0.5

    def jaccard(a: Dict[str, Any], b: Dict[str, Any]) -> float:
        A = set(str(a.get("title","")).lower().split())
        B = set(str(b.get("title","")).lower().split())
        if not A or not B:
            return 0.0
        inter = len(A & B)
        union = len(A | B)
        return inter / union if union else 0.0

    selected: List[Dict[str, Any]] = []
    pool = cands[:]
    while pool and len(selected) < k:
        best, best_score = None, -inf
        for c in pool:
            rel = sim(c)
            red = 0.0
            if selected:
                red = max(jaccard(c, s) for s in selected)
            score = lam * rel - (1 - lam) * red
            if score > best_score:
                best, best_score = c, score
        selected.append(best)
        pool.remove(best)
    return selected

def _reason_for(user_id: str, rec: Dict[str, Any], cur_query: str) -> str:
    prof = PROFILE_STORE.get_profile(user_id)
    last_topics = ", ".join(q for q in prof.get("query_history", [])[-3:])
    title = rec.get("title", "this topic")
    return f"Recommended because you recently asked about {last_topics or cur_query}. This resource covers '{title}'."

def recommend(user_id: str, current_query: str, k: int = 3) -> List[Dict[str, Any]]:
    """
    Returns up to k recommendations that the user hasn't seen, diversified and explained.
    """
    PROFILE_STORE.append_query(user_id, current_query)

    cands = _candidateize(current_query, k=20)
    prof = PROFILE_STORE.get_profile(user_id)
    seen = set(prof.get("seen_resources", []))

    # Filter out seen (by url or id)
    def key(c): return c.get("url") or c.get("id")
    unseen = [c for c in cands if key(c) not in seen]

    # Diversify
    picks = _mmr_select(unseen, k=k, lam=0.7)

    # Build output with reasons
    recs: List[Dict[str, Any]] = []
    for r in picks:
        recs.append({
            "id": r.get("id"),
            "title": r.get("title"),
            "url": r.get("url"),
            "reason": _reason_for(user_id, r, current_query)
        })

    # Mark as seen so we won't recommend them again next time
    PROFILE_STORE.add_seen(user_id, [key(r) for r in picks])

    logger.info(f"[recommend] user={user_id} k={k} picks={len(recs)}")
    return recs
