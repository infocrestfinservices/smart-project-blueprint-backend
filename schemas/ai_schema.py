"""
ai_schema.py

Shared schemas used across all AI agents.
These models ensure consistent communication between
the API, orchestrator, and AI agents.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BusinessInput(BaseModel):
    """
    User input received from the frontend.
    """

    business_name: Optional[str] = Field(
        default=None,
        description="Name of the business."
    )

    business_type: str = Field(
        ...,
        description="Type of business (e.g. Coffee Shop, Salon, Restaurant)."
    )

    industry: Optional[str] = Field(
        default=None,
        description="Industry category."
    )

    location: str = Field(
        ...,
        description="Business location."
    )

    budget: Optional[float] = Field(
        default=None,
        description="Estimated investment budget."
    )

    target_market: Optional[str] = Field(
        default=None,
        description="Primary target audience."
    )

    business_model: Optional[str] = Field(
        default=None,
        description="Business model."
    )

    additional_information: Optional[str] = Field(
        default=None,
        description="Extra details provided by the user."
    )


class AgentResponse(BaseModel):
    """
    Generic response returned by an AI agent.
    """

    success: bool = True

    agent_name: str

    summary: str

    analysis: Dict[str, Any]


class MarketAnalysis(BaseModel):
    market_size: Optional[str] = None
    market_growth: Optional[str] = None
    competitors: List[str] = []
    opportunities: List[str] = []
    challenges: List[str] = []


class SWOTAnalysis(BaseModel):
    strengths: List[str] = []
    weaknesses: List[str] = []
    opportunities: List[str] = []
    threats: List[str] = []


class FeasibilityAnalysis(BaseModel):
    feasibility_score: Optional[int] = None
    investment_required: Optional[str] = None
    expected_roi: Optional[str] = None
    break_even_period: Optional[str] = None
    risks: List[str] = []


class FinalReport(BaseModel):
    """
    Combined report generated after all agents finish.
    """

    business: BusinessInput

    market_analysis: MarketAnalysis

    swot_analysis: SWOTAnalysis

    feasibility_analysis: FeasibilityAnalysis

    executive_summary: str

    recommendations: List[str]