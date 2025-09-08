# =============================================
# File: app/utils/oos.py
# Purpose: Out-of-scope scoring logic
# =============================================

from typing import List, Dict
import os

# Tunable thresholds; start conservative and refine with logs.
SIM_MIN = float(os.getenv("OOS_SIM_MIN", "0.72"))
MARGIN_MIN = float(os.getenv("OOS_MARGIN_MIN", "0.05"))
REQUIRE_TOPK = int(os.getenv("OOS_REQUIRE_TOPK", "2"))

def score(distances: List[float]) -> Dict:
    if not distances:
        return {"oos": True, "reason": "no_results", "sim_top": 0.0, "margin": 0.0}
    sims = [max(0.0, 1.0 - d) for d in distances]
    sims_sorted = sorted(sims, reverse=True)
    sim_top = sims_sorted[0]
    sim_second = sims_sorted[1] if len(sims_sorted) > 1 else 0.0
    margin = sim_top - sim_second if len(sims_sorted) > 1 else sim_top

    # Absolute gate
    if sim_top < SIM_MIN:
        return {"oos": True, "reason": "below_abs_threshold", "sim_top": sim_top, "margin": margin}

    # Margin gate (only if we have >=2 results)
    if len(sims_sorted) >= REQUIRE_TOPK and margin < MARGIN_MIN:
        return {"oos": True, "reason": "below_margin", "sim_top": sim_top, "margin": margin}

    return {"oos": False, "reason": "ok", "sim_top": sim_top, "margin": margin}
