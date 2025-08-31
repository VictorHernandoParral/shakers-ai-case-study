from typing import List, Dict

# Tunable thresholds; start conservative and refine with logs.
SIM_MIN = 0.72         # top similarity must be at least this
MARGIN_MIN = 0.05      # top-1 must beat top-2 by this margin
REQUIRE_TOPK = 2       # need at least 2 retrieved to apply margin

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
