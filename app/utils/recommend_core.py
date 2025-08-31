from pydantic import BaseModel
from typing import List

class RecItem(BaseModel):
    id: str
    title: str
    why: str

class Recommender:
    def recommend(self, user_id: str, current_query: str) -> List[RecItem]:
        # Placeholder deterministic list; replace with embedding similarity + MMR
        items = [
            RecItem(id="kb/banking.md", title="Bank setup", why="Related to payments topic"),
            RecItem(id="kb/contracts.md", title="Freelance contracts", why="Legal basics you may need"),
            RecItem(id="kb/onboarding.md", title="Onboarding", why="Next step after setup"),
        ]
        return items[:3]
