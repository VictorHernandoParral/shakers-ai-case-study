from pydantic import BaseModel
from fastapi import APIRouter
from ..services.recommend import recommend_items

router = APIRouter()

class RecommendRequest(BaseModel):
    user_id: str
    current_query: str

class RecItem(BaseModel):
    id: str
    title: str
    why: str

class RecommendResponse(BaseModel):
    items: list[RecItem]
    latency_ms: int

@router.post("/", response_model=RecommendResponse)
async def post_recommend(payload: RecommendRequest):
    return await recommend_items(payload.user_id, payload.current_query)
