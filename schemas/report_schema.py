from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ReportCreate(BaseModel):
    report_content: str
    report_format: Optional[str] = None
    financial_format: Optional[str] = None

class ReportResponse(BaseModel):
    id: int
    project_id: int
    report_content: Optional[str] = None
    report_format: Optional[str] = None
    financial_format: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True