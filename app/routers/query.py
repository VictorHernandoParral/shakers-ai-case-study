from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
import time
from app.services.retrieval import similarity_search
from app.utils.embeddings import get_embedding_model

router = APIRouter()

class Source(BaseModel):
    id: str
    title: str | None = None
    url: str | None = None

class QueryRequest(BaseModel):
    user_id: str
    query: str
    where: Dict[str, Any] | None = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
    latency_ms: int
    oos: bool = False

def make_answer_english(query: str, contexts: list[str]) -> str:
    """
    Minimal deterministic answer composer in ENGLISH ONLY (no LLM here yet).
    Later we'll swap this for an LLM that is instructed to answer ONLY in English.
    """
    # A super-simple template for now:
    context_snippets = "\n- " + "\n- ".join(ctx[:300] for ctx in contexts) if contexts else ""
    return (
        "Here is what I found:\n"
        f"{context_snippets}\n\n"
        "If you need more detail, please ask a follow-up question in English."
    )

@router.post("/query/", response_model=QueryResponse)
def post_query(body: QueryRequest):
    t0 = time.time()
    docs, metas, sims = similarity_search(body.query, where=body.where)
    sources: list[Source] = []
    for i, m in enumerate(metas):
        sources.append(
            Source(
                id=str(i),
                title=(m.get("title") or m.get("source")),
                url=m.get("source"),
            )
        )
    answer = make_answer_english(body.query, docs)
    latency = int((time.time() - t0) * 1000)
    return QueryResponse(answer=answer, sources=sources, latency_ms=latency, oos=(len(docs) == 0))
