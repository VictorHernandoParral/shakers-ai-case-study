# app/utils/sanitize.py (patch: stronger cue stripping)
from __future__ import annotations
import re
from typing import Iterable

_ALLOWED_SCHEMES = ("http://", "https://", "kb://")
_INJECTION_CUES = [
    "ignore previous instruction",
    "ignore the previous instruction",
    "disregard previous instruction",
    "system prompt",
    "developer message",
    "as an ai",
    "you are chatgpt",
    "act as",
    "do not follow the above",
    "override",
    "reset the system",
    "jailbreak",
]

_WHITESPACE_RE = re.compile(r"\s+")
_SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

def safe_url(url: str) -> str:
    if not url:
        return ""
    u = url.strip()
    if any(u.lower().startswith(s) for s in _ALLOWED_SCHEMES):
        return u
    return ""

def collapse_ws(text: str) -> str:
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", text).strip()

def strip_injection_lines(text: str, cues: Iterable[str] = _INJECTION_CUES) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    cues_l = [c.lower() for c in cues]
    kept = []
    for ln in lines:
        if any(c in ln.lower() for c in cues_l):
            continue
        kept.append(ln)
    return "\n".join(kept)

def _strip_injection_sentences(text: str, cues: Iterable[str] = _INJECTION_CUES) -> str:
    if not text:
        return ""
    parts = _SENT_SPLIT_RE.split(text)
    cues_l = [c.lower() for c in cues]
    kept = [p.strip() for p in parts if p.strip() and not any(c in p.lower() for c in cues_l)]
    if kept:
        return " ".join(kept)
    # fallback: if everything was removed, keep original (we’ll clean inline later)
    return text

def sanitize_context_snippet(text: str, max_chars: int = 800) -> str:
    """
    Collapse whitespace, remove *sentences* that look like prompt-injection,
    and also strip cue phrases inline as a safety net. Then truncate.
    """
    t = _strip_injection_sentences(text)
    # Safety net: remove cue phrases inline if any survived
    for c in _INJECTION_CUES:
        t = re.sub(re.escape(c), "", t, flags=re.IGNORECASE)
    t = collapse_ws(t)
    if max_chars and len(t) > max_chars:
        t = t[:max_chars].rstrip() + "…"
    return t
