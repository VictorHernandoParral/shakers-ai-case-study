import os
from typing import Any, Dict, List, Tuple
import chromadb
from chromadb.config import Settings
from app.utils.embeddings import embed_texts, embed_text

COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "kb-docs")
DEFAULT_TOP_K = int(os.getenv("TOP_K", "4"))
DEFAULT_MIN_SIM = float(os.getenv("MIN_SIMILARITY", "0.78"))  # cosine-sim threshold

def get_client() -> chromadb.Client:
    os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"  # optional: silences telemetry
    persist_dir = os.getenv("CHROMA_DIR", "store/chroma")
    os.makedirs(persist_dir, exist_ok=True)
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False),
    )

def get_collection():
    client = get_client()
    # We store documents and metadata in English only
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,  # we call our own embedder
    )

def _normalize_meta(m: Dict[str, Any], doc_id: str, chunk_idx: int) -> Dict[str, Any]:
    """Ensure minimal metadata fields exist without breaking current callers."""
    m = dict(m or {})
    m.setdefault("doc_id", doc_id)
    m.setdefault("chunk_id", chunk_idx)
    m.setdefault("lang", "en")
    m.setdefault("doctype", "product")  # safest default
    # 'title' and 'source' are used downstream for citations; keep if present
    return m

def upsert_batch(
    ids: List[str],
    documents: List[str],
    metadatas: List[Dict[str, Any]]
) -> None:
    col = get_collection()
    embeddings = embed_texts(documents)
    # Soft-normalize metadata to guarantee filters later (no hard failures)
    norm_metas: List[Dict[str, Any]] = []
    for i, m in enumerate(metadatas):
        norm_metas.append(_normalize_meta(m, doc_id=m.get("doc_id", ids[i]), chunk_idx=m.get("chunk_id", i)))
    col.upsert(ids=ids, documents=documents, metadatas=norm_metas, embeddings=embeddings)

def similarity_search(
    query: str,
    top_k: int = None,
    where: Dict[str, Any] | None = None,
    min_similarity: float | None = None,
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    col = get_collection()
    k = top_k or DEFAULT_TOP_K
    thr = DEFAULT_MIN_SIM if min_similarity is None else float(min_similarity)
    q_emb = embed_text(query)
    res = col.query(
        query_embeddings=[q_emb],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    docs = res["documents"][0] if res["documents"] else []
    metas = res["metadatas"][0] if res["metadatas"] else []
    # Chroma returns distances (smaller is closer for cosine); convert to similarity
    dists = res["distances"][0] if res["distances"] else []
    sims = [1 - d for d in dists]
    # Apply threshold filtering, keep order from Chroma (already sorted)
    filtered = [(d, m, s) for d, m, s in zip(docs, metas, sims) if s >= thr]
    if not filtered:
        return [], [], []
    fd, fm, fs = zip(*filtered)
    return list(fd), list(fm), list(fs)
