import os, uuid, glob, json
from pathlib import Path
from app.services.retrieval import upsert_batch

KB_DIR = os.getenv("KB_DIR", "app/data/kb")
assert os.path.isdir(KB_DIR), f"KB_DIR not found: {KB_DIR}"

def read_files(root: str) -> list[tuple[str, str]]:
    paths = []
    for ext in ("*.md", "*.txt", "*.json"):
        paths += glob.glob(os.path.join(root, "**", ext), recursive=True)

    items = []
    for p in paths:
        if p.endswith(".json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # if it’s a JSON array of strings or objects with "text"
                if isinstance(data, list):
                    for i, it in enumerate(data):
                        text = it.get("text") if isinstance(it, dict) else str(it)
                        if text:
                            items.append((p + f"#{i}", text.strip()))
                else:
                    # Single JSON object with "text"
                    text = data.get("text") if isinstance(data, dict) else ""
                    if text:
                        items.append((p, text.strip()))
            except Exception:
                continue
        else:
            with open(p, "r", encoding="utf-8") as f:
                items.append((p, f.read().strip()))
    return items

def chunk_text(text: str, max_tokens: int = 350, overlap: int = 60) -> list[str]:
    # simple word-based chunker (English only)
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i : i + max_tokens]
        chunks.append(" ".join(chunk))
        i += max_tokens - overlap
    return chunks

def main():
    files = read_files(KB_DIR)
    if not files:
        print("No KB files found. Put ENGLISH content under app/data/kb/")
        return

    ids, docs, metas = [], [], []
    for src, content in files:
        for idx, ch in enumerate(chunk_text(content)):
            ids.append(str(uuid.uuid4()))
            docs.append(ch)
            metas.append({"source": Path(src).as_posix(), "lang": "en"})
            if len(ids) >= 512:  # batch upserts
                upsert_batch(ids, docs, metas)
                ids, docs, metas = [], [], []
    if ids:
        upsert_batch(ids, docs, metas)
    print("KB ready at", os.getenv("CHROMA_DIR", "store/chroma"))

if __name__ == "__main__":
    main()
