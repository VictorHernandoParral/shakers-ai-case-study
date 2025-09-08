# =============================================
# File: app/services/eval.py
# Purpose: Recommendation API endpoint
# =============================================

# Minimal metrics service — expand with real counters


async def get_metrics():
    return {
        "qps": 1.2,
        "avg_latency_ms": 950,
        "oos_rate": 0.18,
        "cache_hit_rate": 0.35,
    }
