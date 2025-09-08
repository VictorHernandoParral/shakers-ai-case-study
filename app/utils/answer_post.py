# =============================================
# File: app/utils/answer_post.py
# Purpose: Utilities to clean LLM answers
# =============================================

# app/utils/answer_post.py
from __future__ import annotations
import re
from typing import Optional

_INTRO_RE = re.compile(r"^\s*(introduction)\s*[:\-]?\s*\n+", re.IGNORECASE)
_LABELS_RE = re.compile(r"\b(question|answer)\s*:\s*", re.IGNORECASE)


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"^[#*\s_>]+|[#*\s_>]+$", "", s)
    s = re.sub(r"[^\w\s]", " ", s)     # drop punctuation
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize(text: str) -> str:
    
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+(\n)", r"\1", text)
    return text.strip()

def _strip_intro_and_labels(text: str) -> str:
    out = _INTRO_RE.sub("", text)
    out = _LABELS_RE.sub("", out)
    return out

def _remove_repeated_question(text: str, query: Optional[str]) -> str:
    if not query:
        return text

    def norm(s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r"[\W_]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    nq = norm(query)
    lines = text.splitlines()
    cleaned, skipped = [], False
    for ln in lines:
        if not skipped and norm(ln) == nq:
            skipped = True
            continue
        cleaned.append(ln)
    return "\n".join(cleaned)

def _strip_leading_question_like(text: str, query: Optional[str]) -> str:
    """
    Remove the first non-empty line if it looks like a question heading
    (bold/heading/punct-insensitive). If a user query is provided, use it as a
    fuzzy guide; otherwise, remove any short question-like heading.
    """
    if not text:
        return text
    lines = text.splitlines()
    # find first non-empty line
    idx = next((i for i, l in enumerate(lines) if l.strip()), None)
    if idx is None:
        return text
    first = lines[idx]
    first_norm = _norm(first)
    qnorm = _norm(query) if query else ""
    looks_question = first.strip().endswith("?") and len(first.strip()) <= 140
    similar = False
    if qnorm:
        if first_norm == qnorm:
            similar = True
        else:
            short, long = (first_norm, qnorm) if len(first_norm) <= len(qnorm) else (qnorm, first_norm)
            similar = short in long and len(short) / max(1, len(long)) >= 0.8
    if looks_question or similar:
        del lines[idx]
        return "\n".join(lines).lstrip("\n")
    return text

def clean_answer(raw_text: str, *, user_query: Optional[str] = None) -> str:
    """
    Elimina 'Introduction', 'Question:', 'Answer:' y cualquier línea que repita la pregunta del usuario.
    También normaliza saltos de línea.
    """
    if not raw_text:
        return raw_text
    text = _strip_intro_and_labels(raw_text)
    # Remove a leading question-like heading (even if it differs from the user query)
    text = _strip_leading_question_like(text, user_query)
    # Drop any standalone line that exactly equals the query
    text = _remove_repeated_question(text, user_query)
    # Strip KB artifacts like "****"
    text = re.sub(r"\s*\*{2,}\s*", " ", text)
    text = _normalize(text)
    # Safety: if we removed too much, fall back to the raw text without labels only)
    if len(text) < 20:
        fallback = _strip_intro_and_labels(raw_text)
        fallback = re.sub(r"\s*\*{2,}\s*", " ", fallback)
        fallback = _normalize(fallback)
        if fallback:
            return fallback
    return text
