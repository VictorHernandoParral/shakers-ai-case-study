from typing import Iterable, List, Dict, Optional, Tuple
import re

# Minimal, model-agnostic token estimator (≈4 chars per token heuristic).
def rough_token_len(text: str) -> int:
    return max(1, len(text) // 4)

def split_by_headings(text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (heading, section_text). If no headings, single chunk.
    Headings: Markdown-style #, ##, ###, or line in ALL CAPS.
    """
    lines = text.splitlines()
    blocks = []
    current_h = "Introduction"
    buf = []
    heading_re = re.compile(r"^(#{1,6}\s+.+)|(^[A-Z0-9 \-_/]{8,}$)")
    for ln in lines:
        if heading_re.match(ln.strip()):
            if buf:
                blocks.append((current_h, "\n".join(buf).strip()))
                buf = []
            current_h = ln.strip().lstrip("# ").strip()
        else:
            buf.append(ln)
    if buf:
        blocks.append((current_h, "\n".join(buf).strip()))
    if not blocks:
        return [("Document", text)]
    return blocks

def chunk_text(
    text: str,
    max_tokens: int = 350,
    overlap_tokens: int = 50,
    min_chunk_tokens: int = 80,
    heading_weight: int = 12,
) -> List[str]:
    """
    Token-aware chunker:
    - splits by headings first
    - within each section, creates rolling windows with overlap
    - injects heading line at the top to keep context
    """
    sections = split_by_headings(text)
    chunks: List[str] = []
    for heading, body in sections:
        if not body.strip():
            continue
        words = body.split()
        # target ~max_tokens minus a small heading allowance
        target = max_tokens - heading_weight
        step = max(1, target - overlap_tokens)
        start = 0
        while start < len(words):
            end = min(len(words), start + target)
            piece = " ".join(words[start:end]).strip()
            if rough_token_len(piece) < min_chunk_tokens and end < len(words):
                # extend until min_chunk_tokens
                extra_end = min(len(words), end + (min_chunk_tokens - rough_token_len(piece)) * 2)
                piece = " ".join(words[start:extra_end]).strip()
                end = extra_end
            chunk = f"{heading}\n\n{piece}"
            chunks.append(chunk)
            if end == len(words):
                break
            start = max(end - overlap_tokens, start + step)
    # Fallback
    if not chunks and text.strip():
        chunks = [text.strip()]
    return chunks
