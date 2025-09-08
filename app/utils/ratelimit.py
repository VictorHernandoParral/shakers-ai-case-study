# =============================================
# File: app/utils/ratelimit.py
# Purpose: In-memory per-key rate limiter
# =============================================

# app/utils/ratelimit.py
# Simple per-key rate limiter (fixed window) with in-memory storage

from __future__ import annotations
import os
import time
from collections import deque
from typing import Dict, Deque

# In-memory store: key -> timestamps deque
_store: Dict[str, Deque[float]] = {}

def _get_limits() -> tuple[int, int]:
    """Read limits at call time so tests/env overrides take effect."""
    max_reqs = int(os.getenv("RL_MAX_REQS", "60"))
    window_s = int(os.getenv("RL_WINDOW_SECONDS", "60"))
    return max_reqs, window_s

def check_rate_limit(key: str) -> None:
    """Raise RuntimeError when rate limited."""
    now = time.time()
    max_reqs, window_s = _get_limits()

    dq = _store.setdefault(key, deque())

    # Drop timestamps outside the window
    cutoff = now - window_s
    while dq and dq[0] < cutoff:
        dq.popleft()

    if len(dq) >= max_reqs:
        raise RuntimeError("Rate limit exceeded")

    dq.append(now)

def reset_rate_limit() -> None:
    """For tests: clear in-memory counters."""
    _store.clear()
