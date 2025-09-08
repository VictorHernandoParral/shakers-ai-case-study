# =============================================
# File: app/utils/prompting.py
# Purpose: Build robust, JSON-structured messages for gpt-4o-mini
# =============================================
from __future__ import annotations
from typing import List, Dict

# Import sanitizers to neutralize prompt-injection in context and URLs
from .sanitize import sanitize_context_snippet, collapse_ws, safe_url

SYS_PROMPT = (
    "You are Shakers’ helpful assistant. Answer ONLY in English and ONLY using the provided CONTEXT. "
    "If the answer is not clearly supported by the CONTEXT, reply exactly: \"I don’t have that information.\" "
    "Output MUST be valid JSON with two fields: {\"answer\": string, \"followups\": string[]}. "
    "Content rules: start with a direct, precise definition or action sentence tailored to THIS question; "
    "then provide an expanded explanation grounded in the CONTEXT (aim for ~180–260 words total). "
    "Prefer short paragraphs and bullet points when they genuinely improve clarity. "
    "Do NOT include headings like 'Introduction', 'Question', or 'Answer'. "
    "Do NOT repeat the user’s question. Do NOT invent facts or URLs. Keep a professional, friendly tone."
)

# User template requesting JSON only
USER_EN_TEMPLATE = (
    "Context (numbered):\\n"
    "{context}\\n\\n"
    "User question:\\n"
    "{question}\\n\\n"
    "Instructions:\\n"
    "- Return ONLY a JSON object with these fields:\\n"
    "  - \"answer\": the final answer text. Start with a direct answer sentence, then expand with a clear rationale, key points, and practical steps or examples as needed (target ~180–260 words).\\n"
    "  - \"followups\": at least 2 short follow-up questions (4–12 words each).\\n"
    "- No markdown outside the JSON. No extra text."
)

def _clean(text: str) -> str:
    if not text:
        return ""
    # Normalize whitespace using shared sanitizer
    return collapse_ws(text)

def _pack_context(sources: List[Dict], max_chars_per_source: int = 450) -> str:
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
    The model must return a JSON object: {"answer": string, "followups": string[]}.
    """
    ctx = _pack_context(sources)
    user = USER_EN_TEMPLATE.format(
        context=ctx if ctx else "(no context)",
        question=query.strip()
    )
    return [
        {"role": "system", "content": SYS_PROMPT},
        {"role": "user", "content": user},
    ]
