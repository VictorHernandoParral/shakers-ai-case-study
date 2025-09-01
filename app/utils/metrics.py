# =============================================
# File: app/utils/metrics.py
# Purpose: In-process counters & histograms for /metrics
# =============================================
from __future__ import annotations
from typing import Dict, Any, List
import threading

# Simple in-memory registry (thread-safe enough for dev)
_lock = threading.Lock()

# Counters
_counters: Dict[str, int] = {
    "requests_total": 0,
    "rate_limit_hits_total": 0,
}

# Labeled counters
_model_usage: Dict[str, int] = {}   # model -> count
_oos_counts: Dict[str, int] = {"true": 0, "false": 0}

# Fixed-bucket histogram for latency (milliseconds)
# Buckets: <=50,100,200,500,1000,2000,5000,10000, +inf
_latency_buckets: List[int] = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
_latency_counts: List[int] = [0 for _ in _latency_buckets] + [0]  # last is +inf (overflow)

def _observe_latency_ms(ms: int) -> None:
    idx = len(_latency_buckets)  # default overflow
    for i, thr in enumerate(_latency_buckets):
        if ms <= thr:
            idx = i
            break
    _latency_counts[idx] += 1

def record_request(latency_ms: int, model: str | None, oos: bool) -> None:
    with _lock:
        _counters["requests_total"] += 1
        _oos_counts["true" if oos else "false"] += 1
        if model:
            _model_usage[model] = _model_usage.get(model, 0) + 1
        _observe_latency_ms(int(latency_ms))

def record_rate_limit_hit() -> None:
    with _lock:
        _counters["rate_limit_hits_total"] += 1

def snapshot() -> Dict[str, Any]:
    with _lock:
        return {
            "counters": dict(_counters),
            "oos": dict(_oos_counts),
            "model_usage": dict(_model_usage),
            "latency_ms": {
                "buckets": list(_latency_buckets) + ["+Inf"],
                "counts": list(_latency_counts),
            },
        }

def reset() -> None:
    with _lock:
        _counters["requests_total"] = 0
        _counters["rate_limit_hits_total"] = 0
        _model_usage.clear()
        _oos_counts["true"] = 0
        _oos_counts["false"] = 0
        for i in range(len(_latency_counts)):
            _latency_counts[i] = 0
