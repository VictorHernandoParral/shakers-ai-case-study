# =============================================
# File: app/services/indexer.py
# Purpose: Rebuild/refresh Chroma vector store from a local KB.
# =============================================
from __future__ import annotations
import os
import glob
import pathlib
from typing import List, Dict, Tuple

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

DEFAULT_KB_DIR = os.getenv("KB_DIR", "app/data/kb/shakers_faq")
DEFAULT_COLLECTION = os.getenv("CHROMA_COLLECTION", "shakers_kb")
DEFAULT_PERSIST = os.getenv("CHROMA_PERSIST_DIR", ".chroma")

# SentenceTransformer embedding (local CPU, no API key required)
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMB = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODEL_NAME)

def _iter_md_files(root: str) -> List[str]:
    root = os.path.normpath(root)
    return sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True))

def _read_utf8(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[str]:
    # simple paragraph packer with overlap
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf: List[str] = []
    cur = 0
    for p in paras:
        if cur + len(p) + 1 > chunk_size and buf:
            chunks.append(" ".join(buf).strip())
            back = max(0, len(chunks[-1]) - overlap)
            # keep a tail for overlap
            tail = chunks[-1][back:]
            buf = [tail, p]
            cur = len(tail) + len(p) + 1
        else:
            buf.append(p)
            cur += len(p) + 1
    if buf:
        chunks.append(" ".join(buf).strip())
    return chunks

def _build_metadata(relpath: str, title: str, source: str, chunk_idx: int) -> Dict:
    return {
        "title": title,
        "source": source,
        "relpath": relpath.replace("\\", "/"),
        "chunk_index": chunk_idx,
        "audience": "",  # extend if you tag files by audience
    }

def _normalize_metadata(md: Dict) -> Dict:
    """Chroma only accepts str|int|float|bool. Coerce None/other types."""
    norm: Dict[str, str | int | float | bool] = {}
    for k, v in md.items():
        if v is None:
            norm[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            norm[k] = v
        else:
            norm[k] = str(v)
    return norm

def refresh_vectors(
    kb_dir: str = DEFAULT_KB_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    persist_dir: str = DEFAULT_PERSIST,
    clear: bool = False,
    chunk_size: int = 800,
    overlap: int = 120,
    source_tag: str = "shakers_faq",
) -> Tuple[int, int]:
    """
    Rebuild a Chroma collection from a local KB directory.
    Returns: (num_files, num_chunks)
    """
    kb_dir = os.path.normpath(kb_dir)
    files = _iter_md_files(kb_dir)
    if not files:
        return (0, 0)

    client = chromadb.Client(Settings(
        persist_directory=persist_dir,
        anonymized_telemetry=False,
    ))

    if clear:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    col = client.get_or_create_collection(
        name=collection_name,
        embedding_function=EMB,
        metadata={"source": source_tag},
    )

    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict] = []

    for path in files:
        text = _read_utf8(path)
        rel = os.path.relpath(path, kb_dir)
        title = pathlib.Path(path).stem
        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for i, ch in enumerate(chunks):
            ids.append(f"{rel}:::{i}")
            docs.append(ch)
            metas.append(_normalize_metadata(_build_metadata(rel, title, source_tag, i)))


    if ids:
        # Chroma can add in batches implicitly; for very large KBs, chunk this.
        col.add(ids=ids, documents=docs, metadatas=metas)

    # Persist to disk
    try:
        client.persist()
    except Exception:
        pass

    return (len(files), len(ids))
