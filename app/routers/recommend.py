# app/routers/recommend.py
from __future__ import annotations
from typing import List, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.recommender import recommend

router = APIRouter()

class RecommendRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=2, max_length=500)

class Recommendation(BaseModel):
    id: str | None = None
    title: str
    url: str
    reason: str

class RecommendResponse(BaseModel):
    recommendations: List[Recommendation]

@router.post("/recommend", response_model=RecommendResponse)
def post_recommend(req: RecommendRequest) -> RecommendResponse:
    """
    Returns 2–3 personalized recommendations based on the user's recent query history.
    - Ensures diversity (MMR) and filters already seen resources.
    - Each recommendation includes a brief explanation (reason).
    """
    try:
        recs = recommend(user_id=req.user_id, current_query=req.query, k=3)
        return RecommendResponse(recommendations=recs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
