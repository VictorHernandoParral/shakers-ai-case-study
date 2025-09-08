# =============================================
# File: app/services/retrieval.py
# Purpose: Retrieval service over Chroma vector DB
# =============================================

# app/services/retrieval.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ---------------------------------------------------------------------
# Chroma client & constants
# ---------------------------------------------------------------------

# Persistent local store (already created in your project)
CHROMA_PATH = "store/chroma"

# One collection for English KB
COLLECTION_NAME = "kb_en"

# Use cosine to be consistent with most sentence-transformers
HNSW_SPACE = "cosine"

# Default model: small + fast and available offline once downloaded
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Singleton Chroma client
_client = chromadb.PersistentClient(path=CHROMA_PATH)


def _get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    """Return a sentence-transformers embedding function for Chroma."""
    return SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


def get_collection():
    """Get or create the KB collection with the configured embedding fn."""
    ef = _get_embedding_function()
    # Chroma v0.5+: pass both metadata (for index space) and embedding_function
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": HNSW_SPACE},
        embedding_function=ef,
    )


# ---------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------

def upsert_batch(
    ids: List[str],
    documents: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    batch_size: int = 256,
) -> None:
    """
    Upsert records in manageable batches.

    Args:
        ids: Stable ids (e.g., "<relpath>#<chunk_idx>").
        documents: Chunk texts.
        metadatas: Per-chunk metadata dicts.
        batch_size: Max records per upsert call.
    """
    if metadatas is None:
        metadatas = [{} for _ in documents]

    col = get_collection()
    n = len(ids)
    for i in range(0, n, batch_size):
        col.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )


# ---------------------------------------------------------------------
# Query / similarity search
# ---------------------------------------------------------------------

def _distance_to_similarity(dist: float, space: str) -> float:
    """
    Convert Chroma distance to a similarity score roughly in [0, 1].

    For cosine, Chroma returns distance = 1 - cosine_sim, so we invert.
    We clamp the value into [0, 1] to avoid tiny numeric artifacts.
    """
    if space == "cosine":
        sim = 1.0 - float(dist)
        return max(0.0, min(1.0, sim))

    # Simple monotonic transforms for other spaces
    if space == "l2":
        sim = 1.0 / (1.0 + float(dist))
        return max(0.0, min(1.0, sim))
    if space in ("ip", "inner_product"):
        sim = 1.0 / (1.0 + float(dist))
        return max(0.0, min(1.0, sim))
    sim = 1.0 - float(dist)
    return max(0.0, min(1.0, sim))


# ---------------- Normalization helpers for the list adapter ---------------- #

def _first_line_title(doc: str, fallback: str = "KB") -> str:
    """Derive a short title from the first non-empty line of a document."""
    if not doc:
        return fallback
    for line in doc.splitlines():
        t = line.strip().lstrip("#").strip()
        if t:
            return t[:120]
    return fallback


def _derive_url(meta: Dict[str, Any]) -> str:
    """
    Prefer an explicit URL from metadata; otherwise, fall back to a stable kb:// URL
    using relpath/path/id so that 'url' is never empty.
    """
    url = (meta.get("url") or "").strip()
    if url:
        return url

    rel = (meta.get("relpath") or meta.get("path") or meta.get("id") or "").strip()
    if rel:
        # Cheap cross-platform basename without importing pathlib
        rel_simple = rel.replace("\\", "/").split("/")[-1]
        return f"kb://{rel_simple}"

    return "kb://source"


def _build_where(
    audience: Optional[str],
    source: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Build Chroma v0.5+ filter dict using operator syntax.

    Examples:
      {"audience": {"$eq": "freelancer"}}
      {"$and": [{"audience": {"$eq": "freelancer"}}, {"source": {"$eq": "shakers_faq"}}]}
    """
    clauses: List[Dict[str, Any]] = []
    if audience:
        clauses.append({"audience": {"$eq": audience}})
    if source:
        clauses.append({"source": {"$eq": source}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


# ----------------------- Core tuple-based retrieval ------------------------- #

def _similarity_search_core_tuple(
    query_text: str,
    audience: Optional[str] = None,
    source: Optional[str] = None,
    min_similarity: float = 0.25,
    top_k: Optional[int] = None,
    k: Optional[int] = None,
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    """
    ORIGINAL tuple-based retrieval:
    returns (documents, metadatas, similarities)
    """
    # Prefer explicit k when provided; otherwise use top_k; default=4
    k_final = 4
    if k is not None:
        k_final = max(0, int(k))
    elif top_k is not None:
        k_final = max(0, int(top_k))

    if k_final == 0:
        return [], [], []

    where = _build_where(audience, source)

    col = get_collection()
    try:
        res = col.query(
            query_texts=[query_text],
            n_results=k_final,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # Robust fallback: no results instead of raising up the stack
        return [], [], []

    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    sims = [_distance_to_similarity(float(d), HNSW_SPACE) for d in dists]

    filtered = [
        (d, m, s) for d, m, s in zip(docs, metas, sims) if s >= float(min_similarity)
    ]
    if not filtered:
        return [], [], []

    fd, fm, fs = zip(*filtered)
    # Preserve the returned order for the core API
    return list(fd)[:k_final], list(fm)[:k_final], list(fs)[:k_final]


# -------------------------- Public tuple API -------------------------------- #

def similarity_search_tuple(
    query_text: str,
    audience: Optional[str] = None,
    source: Optional[str] = None,
    min_similarity: float = 0.25,
    top_k: Optional[int] = None,
    k: Optional[int] = None,
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    """
    Backward-compatible retrieval for internal code: (documents, metadatas, similarities).
    """
    return _similarity_search_core_tuple(
        query_text=query_text,
        audience=audience,
        source=source,
        min_similarity=min_similarity,
        top_k=top_k,
        k=k,
    )


# ---------------------- Public LIST adapter for recommender ----------------- #

def similarity_search(
    query_text: str,
    audience: Optional[str] = None,
    source: Optional[str] = None,
    min_similarity: float = 0.25,
    top_k: Optional[int] = None,
    k: Optional[int] = None,  # alias supported by tests
) -> List[Dict[str, Any]]:
    """
    Return a LIST of normalized candidates. Each item:
    {
      'title': str,
      'url': str,              # always present (falls back to kb://...)
      'similarity': float,     # clamped [0,1]
      'metadata': dict,
      'document': str,         # raw content
      'content': str,          # alias for compatibility with UIs
    }

    The returned list is:
      * deduplicated by URL (first keep the highest-sim item),
      * deterministically ordered by (-similarity, url).
    """
    try:
        docs, metas, sims = _similarity_search_core_tuple(
            query_text=query_text,
            audience=audience,
            source=source,
            min_similarity=min_similarity,
            top_k=top_k,
            k=k,
        )
    except Exception:
        # If the core fails, return an empty list instead of None
        return []

    # Normalize & build items
    raw_items: List[Dict[str, Any]] = []
    for doc, meta, sim in zip(docs or [], metas or [], sims or []):
        meta = dict(meta or {})
        title = (meta.get("title") or meta.get("name") or "").strip() or _first_line_title(doc, "KB")
        url = _derive_url(meta)
        raw_items.append(
            {
                "title": title,
                "url": url,
                "similarity": float(sim),
                "metadata": meta,
                "document": doc or "",
                "content": doc or "",  # alias used by some UIs
            }
        )

    if not raw_items:
        return []

    # Deduplicate by URL keeping the item with the highest similarity.
    by_url: Dict[str, Dict[str, Any]] = {}
    for item in raw_items:
        url = item["url"]
        prev = by_url.get(url)
        if prev is None or item["similarity"] > prev["similarity"]:
            by_url[url] = item

    # Deterministic order: highest similarity first, then URL lexicographically.
    items = list(by_url.values())
    items.sort(key=lambda x: (-x["similarity"], x["url"]))

    return items
