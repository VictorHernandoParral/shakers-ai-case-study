# =============================================
# File: app/services/generation.py
# Purpose: LLM generation with OpenAI (gpt-4o-mini) + OOS guard + citations + style
# =============================================
from __future__ import annotations
import os
from typing import List, Dict, Tuple

from ..utils.prompting import build_messages_en
from ..utils.citations import ensure_citations
from ..utils.answer_style import enforce_style

_OPENAI_AVAILABLE = False
try:
    from openai import OpenAI  # OpenAI Python SDK v1
    _OPENAI_AVAILABLE = True
except Exception:
    pass

DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "600"))
# NEW: timeout & retries
TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_SECONDS", "4"))
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))

OOS_SENTENCE = "I don’t have that information."

def _get_evidence_thresholds() -> tuple[int, int]:
    # Read thresholds from env so tests (and envs) can tune them
    try:
        min_chars = int(os.getenv("LLM_MIN_CHARS", "200"))
    except Exception:
        min_chars = 200
    try:
        min_items = int(os.getenv("LLM_MIN_ITEMS", "2"))
    except Exception:
        min_items = 2
    return min_chars, min_items

def _openai_client():
    if not _OPENAI_AVAILABLE:
        return None
    return OpenAI()

def _enough_evidence(sources: List[Dict], min_chars: int | None = None, min_items: int | None = None) -> bool:
    if not sources:
        return False

    # Pull defaults from env if not explicitly provided
    if min_chars is None or min_items is None:
        cfg_chars, cfg_items = _get_evidence_thresholds()
        if min_chars is None:
            min_chars = cfg_chars
        if min_items is None:
            min_items = cfg_items

    if len(sources) < max(1, min_items):
        return False

    total = sum(len((s.get("content") or "").strip()) for s in sources)
    return total >= max(0, min_chars)

def _fallback_answer(sources: List[Dict]) -> str:
    """Deterministic, safe fallback using compressed sources."""
    joined = " ".join((s.get("content") or "").strip() for s in sources if s.get("content"))
    text = (joined[:500] + ("…" if len(joined) > 500 else ""))
    text = ensure_citations(text, sources)
    text = enforce_style(text, max_sentences=6)
    return text

def _chat_completion_with_retry(client, messages) -> Tuple[str | None, str | None]:
    """
    Try calling OpenAI up to MAX_RETRIES+1 times with TIMEOUT_S each.
    Returns (text, model) or (None, None) if all attempts fail.
    """
    last_err = None
    attempts = max(1, MAX_RETRIES + 1)
    for _ in range(attempts):
        try:
            resp = client.chat.completions.create(
                model=DEFAULT_MODEL,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                messages=messages,
                timeout=TIMEOUT_S,  # SDK v1 supports per-call timeout
            )
            text = (resp.choices[0].message.content or "").strip()
            return text, getattr(resp, "model", DEFAULT_MODEL)
        except Exception as e:
            last_err = e
            continue
    return None, None

def generate_with_llm(query: str, sources: List[Dict]) -> Tuple[str, Dict]:
    """
    Inputs: English query + compressed, reranked sources [{id,title,url,content}]
    Returns: (answer_text, meta)
    meta: {"model": str | None, "oos": bool}
    """
    # 0) Evidence guard
    if not _enough_evidence(sources):
        return OOS_SENTENCE, {"model": None, "oos": True}

    messages = build_messages_en(query, sources)

    # 1) Fallback immediately if SDK/API key missing
    if not _OPENAI_AVAILABLE or not os.getenv("OPENAI_API_KEY"):
        return _fallback_answer(sources), {"model": "fallback-extractive", "oos": False}

    # 2) Real call with retry + timeout
    client = _openai_client()
    text, model = _chat_completion_with_retry(client, messages)

    # 3) If all attempts failed, return graceful fallback (not OOS)
    if not text:
        return _fallback_answer(sources), {"model": "fallback-extractive", "oos": False}

    # 4) Model explicitly declined
    if text.lower().startswith("i don’t have") or text.lower().startswith("i don't have"):
        return OOS_SENTENCE, {"model": model, "oos": True}

    # 5) Ensure citations & style
    text = ensure_citations(text, sources)
    text = enforce_style(text, max_sentences=6)
    return text, {"model": model, "oos": False}
