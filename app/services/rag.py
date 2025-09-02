# =============================================
# File: app/services/rag.py
# Purpose: Retrieval -> Reranking -> Compression -> LLM Answer (English)
# =============================================
import time
from typing import Any, List, Dict

from ..utils.prompts import SYSTEM_PROMPT  # (ok if unused)
from ..utils.retrieval import RetrievalEngine
from ..utils.caching import cache_get, cache_set
from ..utils.reranker import rerank
from ..utils.compressor import compress_chunks
from .generation import generate_with_llm  # local service
from app.utils.oos import score as oos_score
from loguru import logger
from app.services.profiles import PROFILE_STORE

# --- Normalization helpers  ---
import os
import urllib.parse
import pathlib

DOCS_BASE_URL = os.getenv("DOCS_BASE_URL", "").strip()  # optional, for public links

def _fallback_url(id_val: str, title: str) -> str:
    if DOCS_BASE_URL and id_val:
        base = DOCS_BASE_URL if DOCS_BASE_URL.endswith("/") else DOCS_BASE_URL + "/"
        return urllib.parse.urljoin(base, str(id_val).lstrip("/"))
    if id_val:
        return f"kb://{id_val}"
    if title:
        slug = title.lower().strip().replace(" ", "-")
        return f"kb://{slug}"
    return "kb://source"

def _normalize_sources(raw: List[Dict[str, str]], max_n: int = 5) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for s in raw or []:
        title = (s.get("title") or s.get("name") or "KB").strip()
        sid = (s.get("id") or "").strip()
        url = (s.get("url") or "").strip()
        if not url:
            url = _fallback_url(sid, title)
        key = (title, url)
        if key in seen:
            continue
        out.append({"title": title, "url": url})
        seen.add(key)
        if len(out) >= max_n:
            break
    return out

# ---- Retriever and OOS Message ------

retriever = RetrievalEngine()
OOS_MESSAGE = (
    "I don't have information on this. "
    "I am ready to help you with any matter related to the Shakers platform (e.g., payments, project workflow, freelancers, etc.)."
)

# Informative Log regarding OOS
try:
    from app.utils import oos as _oos_cfg
    logger.info(
        f"[OOS.cfg] SIM_MIN={_oos_cfg.SIM_MIN} "
        f"MARGIN_MIN={_oos_cfg.MARGIN_MIN} "
        f"REQUIRE_TOPK={_oos_cfg.REQUIRE_TOPK}"
    )
except Exception:
    pass


def _try_build_chunks_from_ctx(ctx) -> List[Dict[str, str]]:
    """Best-effort adapter for whatever the retriever returns."""
    chunks: List[Dict[str, str]] = []
    sources = getattr(ctx, "sources", None)
    if not sources:
        return chunks
    for s in sources:
        sid = getattr(s, "id", "") or ""
        title = getattr(s, "title", "") or "KB"
        url = getattr(s, "url", "") or ""
        if not url:
            # ensure non-empty, many tests require 'url' key present
            url = _fallback_url(sid, title)
        chunks.append(
            {
                "id": sid,
                "title": title,
                "url": url,
                "content": getattr(s, "content", "") or "",
            }
        )
    return chunks

def _fallback_similarity_search(query: str, k: int = 12) -> List[Dict[str, str]]:
    """Fallback path using the same retrieval that your router already uses."""
    try:
        # lazy import to avoid circulars at import time
        from app.services.retrieval import similarity_search_tuple
        docs, metas, sims = similarity_search_tuple(
            query_text=query,
            audience=None,
            source=None,
            min_similarity=0.0,
            top_k=k,
        )
    except Exception:
        return []

    chunks: List[Dict[str, str]] = []
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        title = meta.get("title") or meta.get("relpath") or meta.get("source") or "KB"
        url = meta.get("url") or (f"kb://{meta.get('relpath')}" if meta.get('relpath') else "")
        # if 'sims' exists; if not, None
        sim_val = None
        try:
            sim_val = float(sims[i]) if sims is not None else None
            # only [0,1]
            if sim_val is not None:
                sim_val = max(0.0, min(1.0, sim_val))
        except Exception:
            sim_val = None

        chunk = {
            "id": str(i),
            "title": title,
            "url": url,
            "content": doc or "",
        }
        # Add OOS signals
        if sim_val is not None:
            chunk["similarity"] = sim_val
            chunk["distance"] = 1.0 - sim_val

        chunks.append(chunk)
    return chunks

def _extract_distances_from_chunks(chunks: List[Dict[str, str]]) -> List[float]:
    """
    Looks for distance or similarity in each chunk:
      - If it exists 'distance' in [0,1].
      - If it exists 'similarity'/'score' in [0,1].
    gives back a list of distances in [0,1].
    """
    distances: List[float] = []
    for ch in chunks or []:
        d = ch.get("distance", None)
        if d is None:
            sim = ch.get("similarity", None)
            if sim is None:
                sim = ch.get("score", None)
            if sim is not None:
                try:
                    sim = float(sim)
                    d = max(0.0, min(1.0, 1.0 - sim))
                except Exception:
                    d = None
        if d is not None:
            try:
                d = float(d)
                d = max(0.0, min(1.0, d))
                distances.append(d)
            except Exception:
                continue
    return distances



async def answer_query(user_id: str, query: str) -> dict[str, Any]:
    t0 = time.perf_counter()

    cache_key = f"q::{query}"
    cached = cache_get(cache_key)
    if cached:
        # Update profile even on cache hit (append query + mark seen)
        try:
            PROFILE_STORE.append_query(user_id, query)
            seen_ids = [s.get("url") or s.get("id") for s in cached.get("sources", [])]
            PROFILE_STORE.add_seen(user_id, [sid for sid in seen_ids if sid])
        except Exception:
            pass
        cached = dict(cached)
        cached["latency_ms"] = int((time.perf_counter() - t0) * 1000)
        return cached

    # 1) Retrieval: prefer engine.search, fallback to vector DB similarity
    raw_chunks: List[Dict[str, str]] = []
    try:
        ctx = retriever.search(query, k=12)
        raw_chunks = _try_build_chunks_from_ctx(ctx)
    except TypeError:
        try:
            ctx = retriever.search(query)
            raw_chunks = _try_build_chunks_from_ctx(ctx)
        except Exception:
            raw_chunks = []
    except Exception:
        raw_chunks = []

    if not raw_chunks:
        raw_chunks = _fallback_similarity_search(query, k=12)

    # 2) OOS gating (if completely empty or distances indicate OOS)
    if not raw_chunks:
        result = {
            "answer": OOS_MESSAGE,
            "sources": [],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "oos": True,
            "model": None,
        }
        # Append query to profile (no 'seen' since we have no sources)
        try:
            PROFILE_STORE.append_query(user_id, query)
        except Exception:
            pass
        cache_set(cache_key, result)
        return result

    distances = _extract_distances_from_chunks(raw_chunks)
    if distances:
        oos_result = oos_score(distances)
        try:
            logger.info(
                f"[OOS] oos={oos_result['oos']} reason={oos_result['reason']} "
                f"sim_top={oos_result.get('sim_top', 0):.3f} margin={oos_result.get('margin', 0):.3f} "
                f"n_hits={len(raw_chunks)} query='{query[:120]}'"
            )
        except Exception:
            pass
        if oos_result["oos"]:
            result = {
                "answer": OOS_MESSAGE,
                "sources": [],
                "latency_ms": int((time.perf_counter() - t0) * 1000),
                "oos": True,
                "model": None,
            }
            try:
                PROFILE_STORE.append_query(user_id, query)
            except Exception:
                pass
            cache_set(cache_key, result)
            return result

    # 3) Rerank & compress
    top_chunks = rerank(query, raw_chunks, top_k=min(4, len(raw_chunks)))
    compressed_chunks = compress_chunks(query, top_chunks, max_sentences=2)

    # 4) Generate with LLM
    answer, meta = generate_with_llm(query, compressed_chunks)

    # 5) Normalize sources (guarantee 'title' + 'url')
    result_sources = _normalize_sources(compressed_chunks, max_n=5)

    result = {
        "answer": answer,
        "sources": result_sources,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
        "oos": bool(meta.get("oos")),
        "model": meta.get("model"),
    }

    # 6) Update profile (append query + mark returned sources as seen)
    try:
        PROFILE_STORE.append_query(user_id, query)
        seen_ids = [s.get("url") for s in result_sources if s.get("url")]
        PROFILE_STORE.add_seen(user_id, seen_ids)
    except Exception:
        pass

    cache_set(cache_key, result)
    return result
