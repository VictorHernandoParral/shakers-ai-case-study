from typing import Dict, Optional
from pathlib import Path
import datetime as dt

def normalize_topic(path: Path) -> str:
    # Example: payments, onboarding, refunds, etc. from folder or file stem
    parts = [p.lower() for p in path.parts if p and p.isascii()]
    # pick folder under /app/data/kb/<topic> or fallback to file stem
    try:
        idx = parts.index("kb")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    except ValueError:
        pass
    return path.stem.lower().replace(" ", "_")

def build_metadata(
    file_path: str,
    *,
    language: str = "en",
    source: str = "internal_kb",
    url: Optional[str] = None,
    title: Optional[str] = None,
    topic: Optional[str] = None,
) -> Dict:
    p = Path(file_path)
    return {
        "title": title or p.stem,
        "url": url or "",
        "topic": topic or normalize_topic(p),
        "language": language,
        "source": source,
        "filename": p.name,
        "relpath": str(p.as_posix()),
        "ingested_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

# Chroma filter shortcuts
def en_only() -> Dict:
    return {"language": "en"}

def by_topic(topic: str) -> Dict:
    return {"topic": topic.lower()}
