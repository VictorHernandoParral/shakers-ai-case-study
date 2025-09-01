# =============================================
# File: app/utils/rcache.py
# Purpose: Simple in-process TTL cache for /query responses
# =============================================
from __future__ import annotations
import os
import time
from collections import OrderedDict
from typing import Any, Dict, Tuple

# Config
_TTL = int(os.getenv("CACHE_TTL_SECONDS", "600"))           # 10 minutes
_MAX = int(os.getenv("CACHE_MAX_ENTRIES", "1000"))          # max cached entries
_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", ".chroma")   # for index versioning

# Store: key -> (expires_at, value)
_store: "OrderedDict[str, Tuple[float, Dict[str, Any]]]" = OrderedDict()

def _now() -> float:
    return time.time()

def _normalize_query(q: str) -> str:
    return " ".join((q or "").strip().lower().split())

def _index_version() -> str:
    # Version token based on persist directory mtime; changes on reindex
    try:
        ts = os.path.getmtime(_PERSIST_DIR)
        return str(int(ts))
    except Exception:
        return "0"

def make_key(user_id: str, query: str) -> str:
    return f"{user_id}:{_normalize_query(query)}:{_index_version()}"

def get(key: str) -> Dict[str, Any] | None:
    # prune expired
    now = _now()
    dead = []
    for k, (exp, _) in _store.items():
        if exp < now:
            dead.append(k)
    for k in dead:
        _store.pop(k, None)

    item = _store.get(key)
    if not item:
        return None
    exp, val = item
    if exp < now:
        _store.pop(key, None)
        return None
    # LRU touch: move to end
    _store.move_to_end(key, last=True)
    return val

def set(key: str, value: Dict[str, Any], ttl: int | None = None) -> None:
    exp = _now() + (ttl if ttl is not None else _TTL)
    _store[key] = (exp, value)
    _store.move_to_end(key, last=True)
    # enforce size
    while len(_store) > _MAX:
        _store.popitem(last=False)

def clear() -> None:
    _store.clear()
