# app/routers/query.py
from __future__ import annotations

import time
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

# Use the tuple-returning API and alias it to the expected name
from app.services.retrieval import similarity_search_tuple as similarity_search

from app.utils.reranker import rerank                   # Rerank retrieved chunks by relevance
from app.utils.compressor import compress_chunks        # Extractive compression (few sentences)
from app.services.generation import generate_with_llm   # LLM answer with guaranteed citations
from app.utils.ratelimit import check_rate_limit        # Per-user/IP rate limiting
from app.utils.metrics import record_request, record_rate_limit_hit
from app.utils import rcache  # response cache
from fastapi.responses import StreamingResponse
import re
from app.utils import slog





router = APIRouter(tags=["query"])  # removed prefix to make paths stable


# --------- Schemas ---------

from pydantic import BaseModel, Field, field_validator
from typing import Literal

class QueryRequest(BaseModel):
    """
    Incoming query payload.
    - user_id: who is asking (used for rate limiting; falls back to client IP).
    - query: the user's question (English-only).
    - audience: optional audience filter, e.g., "freelancer" | "company".
    - source: optional KB source name, e.g., "shakers_faq".
    - min_similarity: minimum similarity threshold for initial retrieval.
    - top_k: UI-preferred number of results; we may retrieve more internally to enable reranking.
    """
    user_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=3, max_length=500)
    audience: Optional[Literal["freelancer", "company"]] = None
    source: Optional[str] = None
    min_similarity: float = Field(0.25, ge=0.0, le=1.0)
    top_k: int = Field(4, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def _trim_query(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("query must not be empty")
        return v

class QueryResponse(BaseModel):
    """
    Outgoing response.
    - answer: final answer text (English), with citations ensured.
    - refs: lightweight references for UI (titles, paths, similarity scores, etc.).
    - oos: True if out-of-scope (insufficient evidence in KB).
    """
    answer: str
    refs: List[Dict[str, Any]]
    oos: bool



# --------- (Legacy fallback) deterministic composer (kept just in case) ---------

def make_answer_english(user_query: str, contexts: List[str]) -> str:
    """
    Minimal deterministic answer in ENGLISH ONLY (no LLM).
    Used only when retrieval returns no results.
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
# -------- Streaming SSE ----------------

_SOURCES_RE = re.compile(r"\n\s*Sources:\s", flags=re.IGNORECASE)

def _split_answer_and_sources(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = _SOURCES_RE.search(text)
    if not m:
        return text.strip(), ""
    idx = m.start()
    body = text[:idx].rstrip()
    tail = text[idx:].lstrip("\n")
    return body, tail

def _chunk_text(text: str, max_chars: int = 80):
    buf = []
    cur = 0
    for w in (text or "").split():
        if cur + len(w) + 1 > max_chars and buf:
            yield " ".join(buf)
            buf = [w]
            cur = len(w) + 1
        else:
            buf.append(w)
            cur += len(w) + 1
    if buf:
        yield " ".join(buf)

def _sse(data: str, event: str | None = None) -> str:
    # Basic SSE frame
    if event:
        return f"event: {event}\ndata: {data}\n\n"
    return f"data: {data}\n\n"

# --------- Route ---------

@router.post("/query", response_model=QueryResponse)   # exact /query (when no prefix)
@router.post("/query/", response_model=QueryResponse)  # accept trailing slash (when no prefix)
@router.post("/", response_model=QueryResponse)        # /query/ when mounted with prefix="/query"
@router.post("", response_model=QueryResponse)         # /query (NO redirect when mounted with prefix="/query")
def post_query(req: QueryRequest, request: Request) -> QueryResponse:
    """
    End-to-end QA pipeline:
      retrieve (wider recall) -> rerank -> compress -> LLM generation (citations) -> refs
    Includes per-user/IP rate limiting (HTTP 429 on overflow).
    """
    t0 = time.time()

    # Rate limit: use user_id; fall back to client IP when missing.
    key = req.user_id or (request.client.host if request.client else "anon")
    try:
        check_rate_limit(key)
    except RuntimeError:
        record_rate_limit_hit()
        # add log context for rate-limited case
        request.state.log_context = {
            "user_id": req.user_id,
            "qhash": slog.qhash(req.query),
            "rate_limited": True,
        }
        raise HTTPException(status_code=429, detail="Too Many Requests")

    # base log context (will be completed later)
    request.state.log_context = {
        "user_id": req.user_id,
        "qhash": slog.qhash(req.query),
        "cache_hit": False,
    }

    # ===== Cache lookup (per user+query+index_version) =====
    cache_key = rcache.make_key(req.user_id or "anon", req.query)
    cached = rcache.get(cache_key)
    if cached:
        latency_ms = int((time.time() - t0) * 1000)
        # record metrics as a 'cache' model hit (oos per cached)
        record_request(latency_ms=latency_ms, model="cache", oos=bool(cached.get("oos")))
        # enrich log context for cache hit
        request.state.log_context.update({
            "model": "cache",
            "oos": bool(cached.get("oos")),
            "cache_hit": True,
        })
        return QueryResponse(
            answer=cached["answer"],
            refs=cached["refs"],
            oos=bool(cached["oos"]),
        )

    # 1) Initial retrieval (retrieve more to enable reranking)
    search_k = max(req.top_k, 12)
    docs, metas, sims = similarity_search(
        query_text=req.query,
        audience=req.audience,
        source=req.source,
        min_similarity=req.min_similarity,
        top_k=search_k,
    )

    # No results -> return legacy deterministic fallback (record metrics)
    if not docs:
        latency_ms = int((time.time() - t0) * 1000)
        record_request(latency_ms=latency_ms, model=None, oos=True)
        request.state.log_context.update({
            "model": None,
            "oos": True,
        })
        resp = QueryResponse(
            answer=make_answer_english(req.query, docs),
            refs=[],
            oos=True,
        )
        # Cache OOS fallback as well (reduces repeated retrieval churn)
        rcache.set(cache_key, resp.model_dump())
        return resp

    # 2) Build chunk objects (keep original index for mapping refs)
    raw_chunks: List[Dict[str, Any]] = []
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        title = meta.get("title") or meta.get("relpath") or meta.get("source") or "KB"
        url = meta.get("url") or (f"kb://{meta.get('relpath')}" if meta.get("relpath") else "")
        raw_chunks.append({
            "id": str(i),
            "title": title,
            "url": url,
            "content": doc,
            "_orig_idx": i,
        })

    # 3) Rerank: keep the most relevant subset for generation
    top_chunks = rerank(req.query, raw_chunks, top_k=min(4, len(raw_chunks)))

    # 4) Compress: keep only the most relevant sentences per chunk
    compressed = compress_chunks(req.query, top_chunks, max_sentences=2)

    # 5) LLM generation with guaranteed citations (adds "Sources:" if missing)
    answer, meta = generate_with_llm(req.query, compressed)
    oos = bool(meta.get("oos"))

    # 6) Build refs for UI (based on the reranked subset actually used)
    refs: List[Dict[str, Any]] = []
    for ch in top_chunks:
        i = ch["_orig_idx"]
        m = metas[i]
        # --- ensure 'url' exists in each ref ---
        url = m.get("url") or (f"kb://{m.get('relpath')}" if m.get("relpath") else "kb://source")
        refs.append(
            {
                "id": str(i),
                "title": m.get("title") or m.get("relpath") or m.get("source") or "KB",
                "url": url,  # <— added
                "audience": m.get("audience"),
                "source": m.get("source"),
                "relpath": m.get("relpath"),
                "chunk_index": m.get("chunk_index"),
                "similarity": float(sims[i]) if i < len(sims) else None,
            }
        )

    latency_ms = int((time.time() - t0) * 1000)
    record_request(latency_ms=latency_ms, model=meta.get("model"), oos=oos)
    # complete log context with model/oos
    request.state.log_context.update({
        "model": meta.get("model"),
        "oos": oos,
    })
    resp = QueryResponse(
        answer=answer,
        refs=refs,
        oos=oos,
    )
    # Save to cache
    rcache.set(cache_key, resp.model_dump())
    return resp

# ------------ Endpoint GET for SSE  -----------

@router.get("/query/stream")
@router.get("/query/stream/")
@router.get("/stream")
def get_query_stream(
    request: Request,
    user_id: str,
    query: str,
    audience: Optional[Literal["freelancer", "company"]] = None,
    source: Optional[str] = None,
    min_similarity: float = 0.25,
    top_k: int = 4,
):
    """
    Server-Sent Events (SSE) streaming for /query.
    Emits:
      - data: <answer chunk>
      - event: sources / data: "Sources: ..."
      - event: meta / data: {"oos": bool, "model": str|null}
      - data: [DONE]
    """
    t0 = time.time()

    # Rate limit
    key = user_id or (request.client.host if request.client else "anon")
    try:
        check_rate_limit(key)
    except RuntimeError:
        record_rate_limit_hit()
        raise HTTPException(status_code=429, detail="Too Many Requests")

    # Cache lookup (reuse same key as POST /query)
    from app.utils import rcache
    cache_key = rcache.make_key(user_id or "anon", query)
    cached = rcache.get(cache_key)

    def _run_pipeline():
        # If cached, reuse
        if cached:
            answer = cached.get("answer", "")
            refs = cached.get("refs", [])
            oos = bool(cached.get("oos"))
            model = "cache"
            return answer, refs, {"oos": oos, "model": model}

        # Retrieval
        search_k = max(top_k, 12)
        docs, metas, sims = similarity_search(
            query_text=query,
            audience=audience,
            source=source,
            min_similarity=min_similarity,
            top_k=search_k,
        )

        # No results
        if not docs:
            answer_text = make_answer_english(query, docs)
            refs = []
            meta = {"oos": True, "model": None}
            # Cache OOS
            rcache.set(cache_key, {"answer": answer_text, "refs": refs, "oos": True})
            return answer_text, refs, meta

        # Build chunks
        raw_chunks: List[Dict[str, Any]] = []
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            title = meta.get("title") or meta.get("relpath") or meta.get("source") or "KB"
            url = meta.get("url") or (f"kb://{meta.get('relpath')}" if meta.get("relpath") else "")
            raw_chunks.append({"id": str(i), "title": title, "url": url, "content": doc, "_orig_idx": i})

        # Rerank & compress
        top_chunks = rerank(query, raw_chunks, top_k=min(4, len(raw_chunks)))
        compressed = compress_chunks(query, top_chunks, max_sentences=2)

        # Generate
        answer_text, meta = generate_with_llm(query, compressed)

        # Refs for UI (based on reranked subset)
        refs: List[Dict[str, Any]] = []
        # We don’t need sims here for stream; just titles/paths
        for ch in top_chunks:
            i = ch["_orig_idx"]
            m = metas[i]
            url = m.get("url") or (f"kb://{m.get('relpath')}" if m.get("relpath") else "kb://source")
            refs.append(
                {
                    "id": str(i),
                    "title": m.get("title") or m.get("relpath") or m.get("source") or "KB",
                    "url": url,  # keep parity for stream refs too
                    "audience": m.get("audience"),
                    "source": m.get("source"),
                    "relpath": m.get("relpath"),
                    "chunk_index": m.get("chunk_index"),
                }
            )

        # Cache final
        rcache.set(cache_key, {"answer": answer_text, "refs": refs, "oos": bool(meta.get("oos"))})
        return answer_text, refs, meta

    def event_generator():
        # Run the pipeline once (sync) and then stream its pieces
        answer_text, refs, meta = _run_pipeline()
        body, sources_block = _split_answer_and_sources(answer_text)

        # 1) body chunks
        for chunk in _chunk_text(body, max_chars=80):
            yield _sse(chunk)

        # 2) sources (from answer, or reconstruct if missing)
        if not sources_block:
            # Minimal rebuild (titles only) if necessary
            items = []
            for r in refs:
                title = r.get("title") or "Source"
                rel = r.get("relpath") or ""
                url = r.get("url") or (f"kb://{rel}" if rel else "")
                items.append(f"[{title}]({url})" if url else title)
            if items:
                sources_block = "Sources: " + " · ".join(items)
        if sources_block:
            yield _sse(sources_block, event="sources")

        # 3) meta
        yield _sse(
            data=f'{{"oos": {str(bool(meta.get("oos"))).lower()}, "model": "{meta.get("model") or ""}"}}',
            event="meta",
        )

        # 4) done
        yield _sse("[DONE]")

        # Metrics
        latency_ms = int((time.time() - t0) * 1000)
        record_request(latency_ms=latency_ms, model=meta.get("model") or ("cache" if cached else None), oos=bool(meta.get("oos")))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
