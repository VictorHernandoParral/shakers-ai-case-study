from fastapi import APIRouter
from ..services.eval import get_metrics

router = APIRouter()

@router.get("/")
async def metrics_root():
    return await get_metrics()
