# =============================================
# File: app/utils/recommend_core.py
# Purpose: Core recommender stub
# =============================================

from pydantic import BaseModel
from typing import List, Optional

class RecItem(BaseModel):
    id: str
    title: str
    why: str
    url: Optional[str] = None   # allow linking to KB items (e.g., kb://shakers_faq/...md)

class Recommender:
    def recommend(self, user_id: str, current_query: str) -> List[RecItem]:
        # Placeholder deterministic list; replace with embedding similarity + MMR
        items = [
            RecItem(id="kb-banking",   title="Bank setup",          why="Related to payments",      url="kb://banking.md"),
            RecItem(id="kb-contracts", title="Freelance contracts", why="Legal basics you may need", url="kb://contracts.md"),
            RecItem(id="kb-onboarding",title="Onboarding",          why="Next step after setup",     url="kb://onboarding.md"),
        ]
        return items[:3]
