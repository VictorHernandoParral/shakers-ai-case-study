import time
from typing import Any
from ..utils.recommend_core import Recommender

recommender = Recommender()

async def recommend_items(user_id: str, current_query: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    items = recommender.recommend(user_id, current_query)
    return {
        "items": [i.model_dump() for i in items],
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }
