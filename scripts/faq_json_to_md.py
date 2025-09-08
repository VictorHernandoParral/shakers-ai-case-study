# =============================================
# File: scripts/faq_json_to_md.py
# Purpose: Script to convert Shakers FAQ JSON/JSONL into markdown KB files
# =============================================

# scripts/faq_json_to_md.py

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Dict, Any


KB_ROOT_DEFAULT = Path("app/data/kb")
EXTS = {".json", ".jsonl"}
VALID_AUDIENCES = {"freelancer", "company"}


def load_items(path: Path) -> List[Dict[str, Any]]:
    """Load a list of Q/A dicts from .json or .jsonl."""
    if path.suffix.lower() == ".jsonl":
        items: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items
    # .json
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        # Support { "items": [ ... ] }
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
        raise ValueError(f"Unsupported JSON structure in {path}")


def slugify(text: str, max_len: int = 80) -> str:
    """Create a filesystem-friendly slug."""
    import re

    text = text.strip().lower()
    # Replace quotes and slashes first
    text = text.replace("'", "").replace('"', "")
    # Replace non-word with hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    if not text:
        text = "item"
    if len(text) > max_len:
        text = text[:max_len].rstrip("-")
    return text


def ensure_audience(aud: str | None, fallback: str | None = None) -> str:
    if aud:
        aud_l = aud.strip().lower()
        if aud_l in VALID_AUDIENCES:
            return aud_l
    if fallback:
        fb = fallback.strip().lower()
        if fb in VALID_AUDIENCES:
            return fb
    raise ValueError(
        f"Audience must be one of {sorted(VALID_AUDIENCES)}; got {aud!r} (fallback={fallback!r})"
    )


def coerce_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def sanitize_title(s: str) -> str:
    """Make a safe YAML double-quoted string (escape quotes)."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def iter_markdown_records(
    items: Iterable[Dict[str, Any]],
    audience_override: str | None,
    src_path: Path,
) -> Iterable[Dict[str, Any]]:
    """Yield normalized records with fields ready to write."""
    for idx, it in enumerate(items, start=1):
        q = coerce_str(it.get("question")).strip()
        a = coerce_str(it.get("answer")).strip()

        aud_item = it.get("audience")
        audience = ensure_audience(audience_override, aud_item)

        source = coerce_str(it.get("source")).strip() or "shakers_faq"

        if not q or not a:
            # Skip incomplete rows gracefully
            continue

        slug = slugify(q)
        title = sanitize_title(q)

        yield {
            "ordinal": idx,
            "title": title,
            "slug": slug,
            "question": q,
            "answer": a,
            "audience": audience,
            "source": source,
            "src_file": str(src_path),
        }


def write_md(
    root_out: Path,
    rec: Dict[str, Any],
) -> Path:
    """Write a single markdown file with YAML front-matter and body."""
    out_dir = root_out / "shakers_faq" / rec["audience"]
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{rec['ordinal']:03d}-{rec['slug']}.md"
    out_path = out_dir / filename

    # Front matter + content
    fm = (
        "---\n"
        f'title: "{rec["title"]}"\n'
        f"audience: {rec['audience']}\n"
        f"source: {rec['source']}\n"
        f"ordinal: {rec['ordinal']}\n"
        f"relpath: shakers_faq/{rec['audience']}/{filename}\n"
        "tags: [faq]\n"
        "---\n\n"
    )

    body = (
        f"# {rec['question']}\n\n"
        f"**Q:** {rec['question']}\n\n"
        f"**A:** {rec['answer']}\n"
    )

    with out_path.open("w", encoding="utf-8", errors="ignore") as f:
        f.write(fm)
        f.write(body)

    return out_path


def convert_file(src_path: Path, out_root: Path, audience_override: str | None) -> int:
    """Convert one input file into many markdown files. Returns count written."""
    items = load_items(src_path)
    count = 0
    for rec in iter_markdown_records(items, audience_override, src_path):
        write_md(out_root, rec)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Shakers FAQ JSON/JSONL to Markdown files with front-matter."
    )
    parser.add_argument(
        "--in",
        dest="in_dir",
        required=True,
        help="Input folder containing .json or .jsonl files.",
    )
    parser.add_argument(
        "--out",
        dest="out_dir",
        default=str(KB_ROOT_DEFAULT),
        help=f"Output KB root (default: {KB_ROOT_DEFAULT})",
    )
    parser.add_argument(
        "--aud",
        dest="audience",
        default=None,
        help="Optional audience override for ALL items in each processed file "
             "(one of: freelancer|company). If omitted, each item must include 'audience'.",
    )
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    audience_override = None
    if args.audience:
        audience_override = ensure_audience(args.audience)

    files = sorted([p for p in in_dir.rglob("*") if p.suffix.lower() in EXTS])
    if not files:
        print(f"No input files with extensions {sorted(EXTS)} found in {in_dir}")
        return

    total = 0
    for p in files:
        wrote = convert_file(p, out_dir, audience_override)
        print(f"[OK] {p} → {wrote} markdown files")
        total += wrote

    print(f"Done. Wrote {total} markdown files under {out_dir}/shakers_faq/.")


if __name__ == "__main__":
    main()
