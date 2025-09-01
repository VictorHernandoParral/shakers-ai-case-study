# scripts/index_kb.py
import re
from pathlib import Path
from typing import Dict, List, Tuple
from app.services.retrieval import get_collection
from app.utils.chunking import chunk_text
from app.utils.metadata import build_metadata

KB_ROOT = Path("app/data/kb")
EXTS = {".md", ".txt"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def read_text(path: Path) -> Tuple[Dict, str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    m = FM_RE.match(raw)
    fm: Dict[str, str] = {}
    if m:
        fm_block = m.group(1)
        for line in fm_block.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"').strip("'")
        body = raw[m.end():]
    else:
        body = raw
    return fm, body

def enumerate_docs() -> List[Path]:
    return [p for p in KB_ROOT.rglob("*") if p.suffix.lower() in EXTS]

def main():
    col = get_collection()  # should point to 'kb_en' and store/chroma
    files = enumerate_docs()
    if not files:
        print("No documents found under app/data/kb.")
        return

    ids, docs, metas = [], [], []
    for file_path in files:
        fm, body = read_text(file_path)
        if not body.strip():
            continue

        # token-aware chunking from your util
        chunks = chunk_text(body, max_tokens=350, overlap_tokens=60)

        base_meta = build_metadata(str(file_path), language="en", source=fm.get("source") or "internal_kb")
        # merge front-matter fields (audience, title, etc.)
        for k, v in fm.items():
            if k not in base_meta:
                base_meta[k] = v

        rel = base_meta.get("relpath") or str(file_path).replace("\\", "/")
        for i, ch in enumerate(chunks):
            cid = f"{rel}#{i:04d}"
            m = dict(base_meta)
            m["chunk_index"] = i
            m["chunk_count"] = len(chunks)
            ids.append(cid)
            docs.append(ch)
            metas.append(m)

    # upsert in batches
    BATCH = 256
    for i in range(0, len(ids), BATCH):
        col.upsert(
            ids=ids[i:i+BATCH],
            documents=docs[i:i+BATCH],
            metadatas=metas[i:i+BATCH],
        )
        print(f"Upserted {min(i+BATCH, len(ids))}/{len(ids)}")

if __name__ == "__main__":
    main()
