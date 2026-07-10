from pydantic import BaseModel
from typing import Optional

class PurposeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    best_for: Optional[str] = None
    recommended_when: Optional[str] = None
    icon: Optional[str] = None

    class Config:
        from_attributes = True