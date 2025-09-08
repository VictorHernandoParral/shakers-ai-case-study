# =============================================
# File: app/routers/metrics_dashboard.py
# Purpose: HTML dashboard that visualizes /metrics JSON
# =============================================
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Point Jinja to the project's templates folder
BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@router.get("/metrics/dashboard", response_class=HTMLResponse, include_in_schema=False)
def metrics_dashboard(request: Request):
    """
    Render the HTML dashboard. The page fetches JSON from GET /metrics
    and auto-refreshes at a fixed interval on the client side.
    """
    return templates.TemplateResponse(
        "metrics.html",
        {
            "request": request,
            # Where the JS should fetch metrics from (relative path works through the same origin)
            "metrics_endpoint": "/metrics",
            # Auto refresh interval (ms)
            "refresh_interval_ms": 5000,
            "app_name": "Shakers AI",
        },
    )
