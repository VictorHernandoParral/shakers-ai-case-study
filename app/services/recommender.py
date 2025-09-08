# =============================================
# File: app/services/recommender.py
# Purpose: Recommender service that generates candidate resources via retrieval or KB scan
# =============================================

# app/services/recommender.py
from __future__ import annotations
from typing import Any, Dict, List
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
        glob.glob(os.path.join(base, "**", "*.md"), recursive=True)
        + glob.glob(os.path.join(base, "**", "*.txt"), recursive=True)
    )
    cands: List[Dict[str, Any]] = []
    for i, p in enumerate(paths[: max(3 * k, 50)]):  # oversample a bit for diversity, cap
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            rel = os.path.relpath(p, base).replace("\\", "/")
            title = os.path.splitext(os.path.basename(p))[0].replace("_", " ").title()
            url = f"kb://{rel}"
            cands.append(
                {
                    "id": f"kbfile-{i}",
                    "title": title or "KB",
                    "url": url,
                    "content": text[:2000],  # small preview is enough
                    # No similarity here; MMR falls back to a flat prior (0.5)
                }
            )
        except Exception:
            continue
    return cands


def _candidateize(query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Get candidate resources for recommendation using the regular similarity_search.
    If empty, fall back to scanning KB files so we always have something to recommend.
    """
    try:
        chunks = similarity_search(query, k=k) or []
    except Exception:
        chunks = []

    if not chunks:
        chunks = _kb_file_candidates(k=k)  # robust fallback

    # dedupe by (url or id)
    uniq = {}
    for c in chunks:
        key = c.get("url") or c.get("id")
        if key and key not in uniq:
            uniq[key] = c
    return list(uniq.values())

def _norm(s: str) -> str:
    import re
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def _looks_like_same_topic(cand: Dict[str, Any], query: str) -> bool:
    """
    Heuristic to avoid recommending the exact topic the user just asked.
    Compares normalized strings; treats strong containment (~same question) as same topic.
    """
    t = _norm(cand.get("title", "")) or _norm(cand.get("url", "")) or _norm(cand.get("id", ""))
    q = _norm(query)
    if not t or not q:
        return False
    if t == q:
        return True
    short, long = (t, q) if len(t) <= len(q) else (q, t)
    return short in long and len(short) / max(1, len(long)) >= 0.8


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
        A = set(str(a.get("title", "")).lower().split())
        B = set(str(b.get("title", "")).lower().split())
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

    # Larger candidate pool (env override: REC_CANDIDATE_K)
    CAND_K = int(os.getenv("REC_CANDIDATE_K", "30"))
    cands = _candidateize(current_query, k=CAND_K)
    prof = PROFILE_STORE.get_profile(user_id)
    seen = set(prof.get("seen_resources", []))

    # Filter out seen (by url or id)
    def key(c): return c.get("url") or c.get("id")
    unseen = [c for c in cands if key(c) not in seen]
    

    # Diversify
    picks = _mmr_select(unseen, k=k, lam=0.7)
    # Stage 1 padding: try to fill from remaining UNSEEN leftovers
    need = max(2, k) - len(picks)
    if need > 0:
        chosen_keys = {key(x) for x in picks}
        leftovers = [c for c in unseen if key(c) not in chosen_keys]
        if leftovers:
            extra = _mmr_select(leftovers, k=need, lam=0.5)
            for e in extra:
                ek = key(e)
                if ek not in chosen_keys:
                    picks.append(e); chosen_keys.add(ek)
        need = max(2, k) - len(picks)
        # Stage 2 padding: as a last resort, pad from the FULL candidate pool (even if seen)
        if need > 0:
            others = [c for c in cands if key(c) not in chosen_keys]
            if others:
                extra2 = _mmr_select(others, k=need, lam=0.4)
                for e in extra2:
                    ek = key(e)
                    if ek not in chosen_keys:
                        picks.append(e); chosen_keys.add(ek)

    # Build output with reasons
    recs: List[Dict[str, Any]] = []
    for r in picks:
        recs.append(
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "url": r.get("url"),
                # Match schema field name used by the API/UI
                "why": _reason_for(user_id, r, current_query),
            }
        )

    # Mark as seen so we won't recommend them again next time
    PROFILE_STORE.add_seen(user_id, [key(r) for r in picks])

    logger.info(f"[recommend] user={user_id} k={k} picks={len(recs)}")
    # Final safety: never return fewer than 2 items if we have anything at all
    return recs[:max(2, k)]
