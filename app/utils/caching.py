# =============================================
# File: app/utils/caching.py
# Purpose: In-memory TTL cache with LRU eviction
# =============================================

import time
from typing import Any
from collections import OrderedDict

_TTL = 600
_store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()

def cache_get(key: str):
    now = time.time()
    if key in _store:
        ts, val = _store[key]
        if now - ts < _TTL:
            return val
        _store.pop(key, None)
    return None

def cache_set(key: str, value: Any):
    _store[key] = (time.time(), value)
    if len(_store) > 512:
        _store.popitem(last=False)
