from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProjectCreate(BaseModel):
    title: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    location: Optional[str] = None
    promoter_name: Optional[str] = None
    promoter_experience: Optional[str] = None
    project_description: Optional[str] = None
    target_market: Optional[str] = None
    target_customers: Optional[str] = None
    project_cost: Optional[float] = None
    own_contribution: Optional[float] = None
    loan_amount: Optional[float] = None
    purpose: Optional[str] = None
    government_scheme_name: Optional[str] = None
    report_format: Optional[str] = None
    financial_format: Optional[str] = None

class ProjectResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    industry: Optional[str] = None
    country: Optional[str] = None
    purpose: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True