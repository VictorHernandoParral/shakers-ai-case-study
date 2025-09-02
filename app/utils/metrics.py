# =============================================
# File: app/utils/metrics.py
# Purpose: In-process counters & histograms for /metrics
# =============================================
from __future__ import annotations
from typing import Dict, Any, List
import threading
import time

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
_latency_buckets: List[int] = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
_latency_counts: List[int] = [0 for _ in _latency_buckets] + [0]  # last is +inf (overflow)

# Per-endpoint latency samples (bounded) and counters for avg/p95
_MAX_SAMPLES: int = 1000
_endpoint_latency: Dict[str, List[float]] = {}   # key: "METHOD /path" -> [ms]
_endpoint_counts: Dict[str, int] = {}            # key: "METHOD /path" -> count

def _avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0

def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    idx = int(0.95 * (len(xs) - 1))
    return xs[idx]

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

def record_endpoint(method: str, path: str, latency_ms: float) -> None:
    key = f"{method.upper()} {path}"
    with _lock:
        _endpoint_counts[key] = _endpoint_counts.get(key, 0) + 1
        buf = _endpoint_latency.setdefault(key, [])
        buf.append(float(latency_ms))
        # bound buffer
        if len(buf) > _MAX_SAMPLES:
            del buf[: len(buf) - _MAX_SAMPLES]


def snapshot() -> Dict[str, Any]:
    with _lock:
        perf: Dict[str, Dict[str, float]] = {}
        for key, buf in _endpoint_latency.items():
            perf[key] = {
                "count": float(_endpoint_counts.get(key, 0)),
                "avg_latency_ms": _avg(buf),
                "p95_latency_ms": _p95(buf),
            }
        return {
            "counters": dict(_counters),
            "oos": dict(_oos_counts),
            "model_usage": dict(_model_usage),
            "latency_ms": {
                "buckets": list(_latency_buckets) + ["+Inf"],
                "counts": list(_latency_counts),
            },
            "performance": {
                "endpoints": perf,
                "generated_at": time.time(),
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
