from dataclasses import dataclass
from typing import List
import os
from pathlib import Path

@dataclass
class Source:
    id: str
    title: str
    url: str | None = None

@dataclass
class SearchContext:
    is_oos: bool
    sources: List[Source]
    chunks: List[str]

class RetrievalEngine:
    def __init__(self):
        # TODO: load FAISS/Chroma index here
        self.kb_dir = Path(os.getenv("KB_DIR", "app/data/kb"))

    def search(self, query: str) -> SearchContext:
        # Placeholder: return mocked context from local files
        files = list(self.kb_dir.glob("*.md"))[:3]
        if not files:
            return SearchContext(True, [], [])
        sources = [Source(id=f.name, title=f.stem, url=f"kb://{f.stem}") for f in files]
        chunks = [f.read_text(encoding="utf-8")[:500] for f in files]
        # Naive OOS heuristic: if query is too short or unrelated keywords
        oos = len(query.strip()) < 3
        return SearchContext(oos, sources, chunks)

    def generate_answer(self, query: str, ctx: SearchContext) -> str:
        # Very simple extractive approach for the scaffold
        joined = "\n\n".join(ctx.chunks)[:1200]
        srcs = ", ".join([f"{s.title} ({s.id})" for s in ctx.sources])
        return (
            f"Here is what I found related to your question: \n\n{joined}\n\nSources: {srcs}"
        )
