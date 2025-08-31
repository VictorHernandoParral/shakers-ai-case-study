import os
from typing import Any, Dict, List, Tuple
import chromadb
from chromadb.config import Settings
from app.utils.embeddings import embed_texts, embed_text

COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "kb-docs")

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

def upsert_batch(
    ids: List[str],
    documents: List[str],
    metadatas: List[Dict[str, Any]]
) -> None:
    col = get_collection()
    embeddings = embed_texts(documents)
    col.upsert(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

def similarity_search(
    query: str,
    top_k: int = None,
    where: Dict[str, Any] | None = None
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    col = get_collection()
    k = top_k or int(os.getenv("TOP_K", "4"))
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
    return docs, metas, sims
