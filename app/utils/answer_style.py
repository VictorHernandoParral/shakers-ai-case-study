# =============================================
# File: app/utils/answer_style.py
# Purpose: Enforce answer style: <= N sentences; bulletize simple lists; preserve trailing "Sources:".
# =============================================
from __future__ import annotations
import re
from typing import Tuple


_SOURCES_RE = re.compile(r"\n\s*Sources\s*:\s", flags=re.IGNORECASE)

_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

def _split_answer_and_sources(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    m = _SOURCES_RE.search(text)
    if not m:
        return text, ""
    return text[: m.start()].rstrip(), text[m.start() :].strip()

def _truncate_sentences(text: str, max_sentences: int) -> str:
    if max_sentences <= 0 or not text:
        return text
    parts = _SENT_SPLIT_RE.split(text.strip())
    if len(parts) <= max_sentences:
        return text.strip()
    kept = " ".join(parts[:max_sentences]).strip()
    return kept + "…"

def _looks_semicolon_list(text: str) -> bool:
    # Heuristics
    return (";" in text) and (text.count(". ") <= 2)

def _bulletize_semicolon_list(text: str) -> str:
    items = [i.strip(" ;\n\t") for i in text.split(";")]
    items = [i for i in items if i]
    if len(items) < 3:
        return text
    return "- " + "\n- ".join(items)

def enforce_style(answer_text: str, max_sentences: int = 14) -> str:
    """
    - If the body looks like a list separated by ‘;’, format it as bullet points.
    - Otherwise, trim it to ‘max_sentences’ sentences (default 14).
    - Preserve a final block “Sources: ...” exactly as it is.
    """
    if not answer_text:
        return answer_text or ""

    body, sources_block = _split_answer_and_sources(answer_text)

    
    if _looks_semicolon_list(body):
        body_fmt = _bulletize_semicolon_list(body)
    else:
        body_fmt = _truncate_sentences(body, max_sentences=max_sentences)

    if sources_block:
        return f"{body_fmt}\n\n{sources_block}"
    return body_fmt
