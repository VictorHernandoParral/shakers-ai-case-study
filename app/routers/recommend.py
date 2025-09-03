# app/routers/recommend.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from app.services.recommender import recommend

router = APIRouter(tags=["recommend"])


# ---------- Response schema ----------
class Recommendation(BaseModel):
    id: str | None = None
    title: str
    url: str
    reason: str


class RecommendResponse(BaseModel):
    recommendations: List[Recommendation]


# ---------- Helpers ----------
def _slug(s: str) -> str:
    """Tiny slugifier for fallback URLs."""
    s = (s or "").strip().lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "_", "-", "/", "."):
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "item"


def _coerce_payload(raw: Dict[str, Any]) -> Tuple[str, str]:
    """
    Accept multiple client variants and normalize them.

    Supported forms:
      1) {"user_id": "...", "query": "..."}
      2) {"session_user_id": "...", "question": "..."}  (aliases)
      3) {"question": "...", "ctx": {"session_id": "...", ...}}  <-- Streamlit client

    Returns (user_id, query) or raises HTTPException(422).
    """
    data = dict(raw or {})
    lower = {str(k).lower(): v for k, v in data.items()}

    # try flat first
    user_id = (
        lower.get("user_id")
        or lower.get("session_user_id")
        or lower.get("uid")
        or lower.get("user")
    )
    query = (
        lower.get("query")
        or lower.get("question")
        or lower.get("text")
        or lower.get("q")
    )

    # then look into ctx if missing
    ctx = lower.get("ctx")
    if (not user_id) and isinstance(ctx, dict):
        ctx_lower = {str(k).lower(): v for k, v in ctx.items()}
        user_id = (
            ctx_lower.get("session_id")
            or ctx_lower.get("user_id")
            or ctx_lower.get("session_user_id")
            or ctx_lower.get("uid")
        )

    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=422, detail="Missing user identifier.")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=422, detail="Missing query text.")

    return user_id.strip(), query.strip()


def _normalize_recs(recs: List[Dict[str, Any]]) -> List[Recommendation]:
    """
    Guarantee a stable, normalized list and always build a URL when missing.
    This ensures client-side 'seen' tracking and deduping are consistent.
    """
    normalized: List[Recommendation] = []
    for r in recs or []:
        if not r:
            continue
        rid = r.get("id")
        title = str(r.get("title", "")).strip() or "Untitled"
        url = str(r.get("url", "")).strip()
        reason = str(r.get("reason", "")).strip() or str(r.get("why", "")).strip()

        # Fallback URL so there's always a stable identifier to track
        if not url:
            anchor = str(rid or title)
            url = f"kb://{_slug(anchor)}"

        normalized.append(Recommendation(id=(rid if isinstance(rid, str) else None),
                                         title=title, url=url, reason=reason))
    return normalized


# ---------- Endpoint ----------
@router.post("/recommend", response_model=RecommendResponse)
def post_recommend(payload: Dict[str, Any] = Body(...)) -> RecommendResponse:
    """
    Personalized Recommendation Service.

    Input: user's current query (+ implicit profile/history on server).
    Output: 2–3 items, each with {id, title, url, reason}.
    """
    try:
        user_id, query = _coerce_payload(payload)
        recs = recommend(user_id=user_id, current_query=query, k=3) or []
        return RecommendResponse(recommendations=_normalize_recs(recs))
    except HTTPException:
        # pass through validation errors
        raise
    except Exception as e:
        # Keep details for debugging; middleware will log request context.
        raise HTTPException(status_code=500, detail=str(e))
