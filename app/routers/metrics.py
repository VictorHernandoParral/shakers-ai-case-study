# =============================================
# File: app/routers/metrics.py
# Purpose: Expose internal metrics as JSON
# =============================================
from __future__ import annotations
from fastapi import APIRouter
from app.utils.metrics import snapshot

router = APIRouter(tags=["metrics"])

@router.get("/metrics")
def get_metrics():
    """Return in-process metrics (JSON)."""
    return snapshot()
