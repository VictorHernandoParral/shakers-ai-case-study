from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)

from .routers import query, recommend, metrics
import time
from app.utils import slog
from app.routers import recommend as recommend_router
from app.utils.metrics import record_request, record_endpoint

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Shakers AI Case Study",
    # we'll serve our own docs so we can brand them
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

# 1) Serve /static
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 2) Jinja templates
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 3) Home page "/"
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 4) Favicon for browsers (handles GET /favicon.ico)
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(BASE_DIR / "static" / "branding" / "favicon.ico")

# 5) Custom Swagger UI that uses your favicon + CSS
@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="Shakers API – Docs",
        swagger_favicon_url="/static/branding/favicon.ico",
        swagger_css_url="/static/branding/swagger.css",  # put your CSS here
    )

@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()

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

# Home 
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    # If not template we address Swagger as fallback
    index_html = TEMPLATES_DIR / "index.html"
    if not index_html.exists():
        return RedirectResponse(url="/docs")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "app_name": "Shakers AI"}
    )

# Favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav = STATIC_DIR / "branding" / "favicon.ico"
    if fav.exists():
        return FileResponse(fav)
    # fallback: 204
    return HTMLResponse(status_code=204)


app.include_router(query.router, prefix="/query", tags=["query"])        # :contentReference[oaicite:0]{index=0}
app.include_router(recommend.router, prefix="/recommend", tags=["recommend"])  # :contentReference[oaicite:1]{index=1}
app.include_router(metrics.router)  #   :contentReference[oaicite:2]{index=2}
app.include_router(recommend_router.router)
