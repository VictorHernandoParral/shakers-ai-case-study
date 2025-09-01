# =============================================
# File: app/utils/prompting.py
# Purpose: Build robust, style-enforcing messages for gpt-4o-mini
# =============================================
from __future__ import annotations
from typing import List, Dict

# Import sanitizers to neutralize prompt-injection in context and URLs
from .sanitize import sanitize_context_snippet, collapse_ws, safe_url

SYS_PROMPT = (
    "You are a precise, terse support assistant for the Shakers platform. "
    "Answer ONLY in English. Use ONLY the provided CONTEXT. "
    "If the answer is not clearly supported by the CONTEXT, reply exactly: "
    "\"I don’t have that information.\" "
    "Style rules: keep answers <= 6 sentences; if you list multiple items, use bullet points. "
    "When appropriate, include concise references by title in-line like [Title](URL). "
    "Do not invent facts or URLs. Do not speculate."
)

def _clean(text: str) -> str:
    if not text:
        return ""
    # Normalize whitespace using shared sanitizer
    return collapse_ws(text)

def _pack_context(sources: List[Dict], max_chars_per_source: int = 800) -> str:
    """
    Pack sources as numbered sections with sanitized content and safe URLs.
    """
    lines: List[str] = []
    for idx, s in enumerate(sources, start=1):
        title = _clean(s.get("title") or "KB")
        url = safe_url((s.get("url") or "").strip())  # sanitize URL (allow http/https/kb only)
        # Sanitize context text: strip injection sentences, collapse ws, and truncate
        content = sanitize_context_snippet(s.get("content") or "", max_chars=max_chars_per_source)

        header = f"[{idx}] Title: {title}"
        if url:
            header += f" | URL: {url}"
        lines.append(header)
        if content:
            lines.append(f"Content: {content}")
    return "\n".join(lines)

def build_messages_en(query: str, sources: List[Dict]) -> List[Dict]:
    """
    Returns messages suitable for OpenAI Chat Completions API.
    """
    ctx = _pack_context(sources)
    user = (
        f"QUESTION: {query.strip()}\n\n"
        "CONTEXT (numbered):\n"
        f"{ctx if ctx else '(no context)'}\n\n"
        "INSTRUCTIONS:\n"
        "- Use ONLY the CONTEXT above.\n"
        "- If unsure or missing information, reply exactly: \"I don’t have that information.\"\n"
        "- Keep answers <= 6 sentences; use bullet points for multi-item lists.\n"
        "- Prefer brief inline references like [Title](URL) if present in CONTEXT."
    )
    return [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": user},
    ]
