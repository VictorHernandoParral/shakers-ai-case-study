# =============================================
# File: app/eval/harness.py
# Purpose: Offline evaluation harness for the Shakers RAG pipeline.
# =============================================
from __future__ import annotations
import os
import sys
import re
import time
import argparse
import asyncio
import json
from typing import Any, Dict, List

# Ensure project root on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

# --- Optional .env loader (no hard dep) ---
def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass

from app.services import rag  # uses answer_query(user_id, query)

SOURCES_RE = re.compile(r"\n\s*Sources:\s", re.IGNORECASE)
SENT_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

def _split_body_and_sources(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    m = SOURCES_RE.search(text)
    if not m:
        return text.strip(), ""
    idx = m.start()
    return text[:idx].strip(), text[idx:].strip()

def _count_sentences(body: str) -> int:
    if not body:
        return 0
    body = " ".join(body.split())
    parts = SENT_SPLIT_RE.split(body.strip())
    return len([p for p in parts if p])

def _load_cases(path: str) -> List[Dict[str, Any]]:
    import yaml  # local import to avoid hard dep elsewhere
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

async def _eval_one(case: Dict[str, Any], use_api: bool) -> Dict[str, Any]:
    # Control API usage for reproducibility
    if not use_api:
        os.environ.pop("OPENAI_API_KEY", None)

    q = case["query"]
    t0 = time.perf_counter()
    result = await rag.answer_query(user_id=case.get("user_id", "eval"), query=q)
    dt_ms = int((time.perf_counter() - t0) * 1000)

    ans = result.get("answer", "") or ""
    body, sources_block = _split_body_and_sources(ans)

    # Metrics
    answered = not result.get("oos", False)
    has_citations = bool(sources_block) or ("[http" in ans.lower()) or ("](" in ans)
    sent_ok = _count_sentences(body) <= 6 or body.strip().startswith("- ")

    must_include = [s.lower() for s in case.get("must_include", [])]
    contains_expected = all(s in ans.lower() for s in must_include)

    # --- read refs OR sources (router vs rag service) ---
    refs_raw = result.get("refs")
    if refs_raw is None:
        refs_raw = result.get("sources", [])  # <- support rag.answer_query
    ref_titles = [str(r.get("title", "")).lower() for r in refs_raw]

    titles_expect = [s.lower() for s in case.get("expect_titles_contains", [])]
    cites_expected = any(any(tok in title for tok in titles_expect) for title in ref_titles) if titles_expect else True

    return {
        "id": case.get("id", q[:40]),
        "answered": answered,
        "has_citations": has_citations,
        "style_ok": sent_ok,
        "contains_expected": contains_expected,
        "cites_expected": cites_expected,
        "latency_ms": result.get("latency_ms", dt_ms),
        "model": result.get("model", None),
        "refs_used": ref_titles[:5],
    }

def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def rate(key: str) -> float:
        ok = sum(1 for r in rows if r.get(key))
        return round(100.0 * ok / max(1, len(rows)), 1)

    return {
        "n": len(rows),
        "answered_%": rate("answered"),
        "citations_%": rate("has_citations"),
        "style_ok_%": rate("style_ok"),
        "contains_expected_%": rate("contains_expected"),
        "cites_expected_%": rate("cites_expected"),
        "avg_latency_ms": int(sum(r.get("latency_ms", 0) for r in rows) / max(1, len(rows))),
        "models": sorted(set(filter(None, (r.get("model") for r in rows)))),
    }

def main():
    ap = argparse.ArgumentParser(description="Evaluate the Shakers RAG pipeline.")
    ap.add_argument("--cases", default="tests/data/eval_cases.yaml", help="YAML with evaluation cases")
    ap.add_argument("--use-api", action="store_true", help="Call OpenAI API if key is present (default: fallback)")
    ap.add_argument("--max", type=int, default=0, help="Evaluate at most N cases (0 = all)")
    ap.add_argument("--json", action="store_true", help="Print JSON rows (one per line)")
    args = ap.parse_args()

    # Load .env if available so OPENAI_API_KEY is picked up
    _load_dotenv_if_available()

    if args.use_api and not os.getenv("OPENAI_API_KEY"):
        print("[WARN] --use-api set but OPENAI_API_KEY is not defined; will use fallback.", file=sys.stderr)

    if not os.path.exists(args.cases):
        print(f"[ERROR] Cases file not found: {args.cases}", file=sys.stderr)
        sys.exit(2)

    cases = _load_cases(args.cases)
    if args.max > 0:
        cases = cases[: args.max]

    rows: List[Dict[str, Any]] = []
    async def run_all():
        for c in cases:
            rows.append(await _eval_one(c, use_api=args.use_api))

    asyncio.run(run_all())

    if args.json:
        for r in rows:
            print(json.dumps(r, ensure_ascii=False))
    else:
        summary = summarize(rows)
        print("\n=== Evaluation Summary ===")
        for k, v in summary.items():
            print(f"{k}: {v}")
        print("\n=== Per-case ===")
        for r in rows:
            print(f"- {r['id']}: answered={r['answered']} citations={r['has_citations']} style_ok={r['style_ok']} "
                  f"contains_expected={r['contains_expected']} cites_expected={r['cites_expected']} "
                  f"latency_ms={r['latency_ms']} model={r.get('model')}")
            if r.get("refs_used"):
                print(f"  refs_used: {r['refs_used']}")

if __name__ == "__main__":
    main()
