"""
financial_engine.calculations.revenue

The Manufacturing Revenue Engine and its models: the reusable projection
timeline, the structured RevenueProjection, and revenue validation.
"""

from .projection_period import ProjectionPeriod, ProjectionTimeline, YearlySeries
from .revenue_engine import ManufacturingRevenueEngine
from .revenue_projection import ProductRevenueLine, RevenueProjection
from .revenue_validator import RevenueValidator

__all__ = [
    "ProjectionPeriod",
    "ProjectionTimeline",
    "YearlySeries",
    "RevenueProjection",
    "ProductRevenueLine",
    "RevenueValidator",
    "ManufacturingRevenueEngine",
]
