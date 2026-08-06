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

class ProjectUpdate(BaseModel):
    """A partial edit. Every field is optional and only the ones actually sent are
    written, so a request carrying one figure can never blank out the rest.
    `title` is optional here (unlike ProjectCreate) but cannot be set to null."""
    title: Optional[str] = None
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
    # Everything ProjectCreate accepts comes back out. It used to return only id/title/
    # industry/country/purpose/status, so the figures the user had entered were saved but
    # never sent to the browser — the report header showed "—" for Total Cost, Own
    # Contribution and Funding Required, and the Edit Details panel opened empty.
    id: int
    user_id: Optional[int] = None
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
    status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True