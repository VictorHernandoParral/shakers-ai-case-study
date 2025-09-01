# app/routers/query.py
from __future__ import annotations

import time
from typing import List, Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.retrieval import similarity_search

router = APIRouter(prefix="/query", tags=["query"])


# --------- Schemas ---------

class QueryRequest(BaseModel):
    user_id: str
    query: str
    audience: Optional[str] = None   # "freelancer" | "company"
    source: Optional[str] = None     # e.g., "shakers_faq"
    min_similarity: float = 0.25
    top_k: int = 4                   # ensure n_results is never None


class QueryResponse(BaseModel):
    answer: str
    refs: List[Dict[str, Any]]
    oos: bool


# --------- Answer composer (English-only for now) ---------

def make_answer_english(user_query: str, contexts: List[str]) -> str:
    """
    Minimal, deterministic answer in ENGLISH ONLY (no LLM yet).
    """
    if not contexts:
        return (
            "I couldn't find a confident answer in the knowledge base. "
            "Please rephrase or provide more detail (in English)."
        )
    bullets = "\n- " + "\n- ".join(c[:300].strip() for c in contexts)
    return (
        "Here is what I found:\n"
        f"{bullets}\n\n"
        "If you need more detail, please ask a follow-up question in English."
    )


# --------- Route ---------

@router.post("/query/", response_model=QueryResponse)
def post_query(req: QueryRequest) -> QueryResponse:
    t0 = time.time()

    docs, metas, sims = similarity_search(
        query_text=req.query,
        audience=req.audience,
        source=req.source,
        min_similarity=req.min_similarity,
        top_k=req.top_k,
    )

    # Build lightweight refs for the UI
    refs: List[Dict[str, Any]] = []
    for i, m in enumerate(metas):
        refs.append(
            {
                "id": str(i),
                "title": m.get("title") or m.get("relpath") or m.get("source") or "KB",
                "audience": m.get("audience"),
                "source": m.get("source"),
                "relpath": m.get("relpath"),
                "chunk_index": m.get("chunk_index"),
                "similarity": float(sims[i]) if i < len(sims) else None,
            }
        )

    answer = make_answer_english(req.query, docs)
    oos = len(docs) == 0

    # (We keep the response schema minimal: answer, refs, oos)
    return QueryResponse(answer=answer, refs=refs, oos=oos)
