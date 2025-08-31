from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import query, recommend, metrics

app = FastAPI(title="Shakers AI — Support & Recommendations", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(query.router, prefix="/query", tags=["query"])
app.include_router(recommend.router, prefix="/recommend", tags=["recommend"]) 
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"]) 
