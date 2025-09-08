# =============================================
# File: app/utils/citations.py
# Purpose: Ensure answers include citations
# =============================================
from __future__ import annotations
from typing import List, Dict
from .sanitize import safe_url

def _dedupe_sources(sources: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for s in sources:
        key = (s.get("url") or "").strip().lower() or (s.get("title") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(s)
    return result

def ensure_citations(answer: str, sources: List[Dict], append_block: bool = False) -> str:
    """
    If the model didn't add inline citations like [Title](URL),
    append a 'Sources:' line with the title of the faq source.
    """
    if not append_block or not sources:
        return answer or ""

    text = answer or ""
    low = text.lower()
    
    if "[" in low and "](" in low:
        return text

    items = []
    for s in _dedupe_sources(sources):
        title = (s.get("title") or "Source").strip()
        url = safe_url(s.get("url") or "")
        items.append(f"[{title}]({url})" if url else title)

    if not items:
        return text

    sep = " · "
    return f"{text.rstrip()}\n\nSources: {sep.join(items)}"
