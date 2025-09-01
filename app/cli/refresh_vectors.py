# =============================================
# File: app/cli/refresh_vectors.py
# Purpose: CLI entrypoint to refresh Chroma vectors from a KB folder.
# Usage:
#   poetry run python -m app.cli.refresh_vectors --kb app/data/kb/shakers_faq --collection shakers_kb --clear
# =============================================
from __future__ import annotations
import argparse
import sys
from app.services.indexer import refresh_vectors, DEFAULT_KB_DIR, DEFAULT_COLLECTION, DEFAULT_PERSIST

def main(argv=None):
    ap = argparse.ArgumentParser(description="Refresh vectors from a KB folder into Chroma.")
    ap.add_argument("--kb", default=DEFAULT_KB_DIR, help="KB root directory (default: app/data/kb/shakers_faq)")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION, help="Chroma collection name (default: shakers_kb)")
    ap.add_argument("--persist", default=DEFAULT_PERSIST, help="Chroma persist dir (default: .chroma)")
    ap.add_argument("--chunk-size", type=int, default=800, help="Chunk size in characters (default: 800)")
    ap.add_argument("--overlap", type=int, default=120, help="Overlap in characters (default: 120)")
    ap.add_argument("--clear", action="store_true", help="Drop collection before re-adding all vectors")
    args = ap.parse_args(argv)

    files, chunks = refresh_vectors(
        kb_dir=args.kb,
        collection_name=args.collection,
        persist_dir=args.persist,
        clear=args.clear,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )

    if files == 0:
        print("[WARN] No markdown files found. Check --kb path.", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] Indexed {files} files into '{args.collection}' ({chunks} chunks). Persist: {args.persist}")

if __name__ == "__main__":
    main()
