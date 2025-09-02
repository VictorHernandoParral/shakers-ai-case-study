from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import query, recommend, metrics
import time
from app.utils import slog
from app.routers import recommend as recommend_router
from app.utils.metrics import record_request, record_endpoint

app = FastAPI(title="Shakers AI — Support & Recommendations", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def _logging_middleware(request, call_next):
    start = time.perf_counter()
    req_id = slog.new_request_id()
    client_ip = request.client.host if request.client else None
    try:
        response = await call_next(request)
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        ctx = getattr(request.state, "log_context", {})
        slog.log_event(
            "request.error",
            request_id=req_id,
            path=str(request.url.path),
            method=request.method,
            latency_ms=latency_ms,
            client_ip=client_ip,
            error=str(e),
            **(ctx or {}),
        )
        raise
    latency_ms = int((time.perf_counter() - start) * 1000)
    ctx = getattr(request.state, "log_context", {}) or {}
    ctx.setdefault("rate_limited", response.status_code == 429)
    slog.finalize_request_log(
        request_id=req_id,
        method=request.method,
        path=str(request.url.path),
        status=response.status_code,
        latency_ms=latency_ms,
        client_ip=client_ip,
        ctx=ctx,
    )
    # --- metrics wiring ---
    try:
        # best-effort: extract optional fields for model/oos; defaults are safe
        model = ctx.get("model") if isinstance(ctx, dict) else None
        oos = bool(ctx.get("oos", False)) if isinstance(ctx, dict) else False
        record_request(latency_ms=latency_ms, model=model, oos=oos)
        record_endpoint(method=request.method, path=str(request.url.path), latency_ms=latency_ms)
    except Exception:
        pass
    
    try:
        response.headers["X-Request-ID"] = req_id
    except Exception:
        pass
    return response


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(query.router, prefix="/query", tags=["query"])        # :contentReference[oaicite:0]{index=0}
app.include_router(recommend.router, prefix="/recommend", tags=["recommend"])  # :contentReference[oaicite:1]{index=1}
app.include_router(metrics.router)  #   :contentReference[oaicite:2]{index=2}
app.include_router(recommend_router.router)
