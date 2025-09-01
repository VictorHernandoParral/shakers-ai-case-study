# =============================================
# File: app/utils/answer_style.py
# Purpose: Enforce answer style: <= 6 sentences; bulletize lists; preserve citations.
# =============================================
from __future__ import annotations
import re
from typing import Tuple

_SOURCES_RE = re.compile(r"\n\s*Sources:\s", flags=re.IGNORECASE)

_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

def _split_answer_and_sources(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    m = _SOURCES_RE.search(text)
    if not m:
        return text.strip(), ""
    idx = m.start()
    body = text[:idx].rstrip()
    tail = text[idx:].lstrip("\n")
    return body, tail

def _split_sentences(body: str) -> list[str]:
    if not body:
        return []
    body = " ".join(body.split())
    parts = _SENT_SPLIT_RE.split(body.strip())
    return [p.strip() for p in parts if p.strip()]

def _truncate_sentences(body: str, max_sentences: int = 6) -> str:
    sents = _split_sentences(body)
    if len(sents) <= max_sentences:
        return body
    return " ".join(sents[:max_sentences]).rstrip()

def _looks_semicolon_list(body: str) -> bool:
    # Heuristic: 3+ segments separated by semicolons, each reasonably short.
    parts = [p.strip() for p in body.split(";") if p.strip()]
    if len(parts) < 3:
        return False
    return all(len(p) <= 140 for p in parts[:6])

def _bulletize_semicolon_list(body: str) -> str:
    parts = [p.strip().rstrip(".") for p in body.split(";") if p.strip()]
    return "\n- " + "\n- ".join(parts)

def enforce_style(answer_text: str, max_sentences: int = 6) -> str:
    """
    Enforce:
      - <= max_sentences in the main body.
      - Bulletize if body looks like a semicolon-separated list.
      - Preserve any trailing "Sources: ..." block exactly as-is.
    """
    if not answer_text:
        return answer_text or ""

    body, sources_block = _split_answer_and_sources(answer_text)

    # Try bulletization first (only if it clearly looks like a list)
    if _looks_semicolon_list(body):
        body_fmt = _bulletize_semicolon_list(body)
    else:
        # Otherwise, truncate sentences if necessary
        body_fmt = _truncate_sentences(body, max_sentences=max_sentences)

    if sources_block:
        return f"{body_fmt}\n\n{sources_block}"
    return body_fmt
