"""
revenue_projection.py

The structured output of the Revenue Engine. Deliberately NOT a single revenue
number: it keeps every intermediate step (capacity → utilisation → production →
yield → scrap → saleable → price → revenue) per product AND per year, so the
result is fully auditable and reusable by reports, dashboards and downstream
engines.

Multi-product by design — a business with Product A / B / C is just a list of
ProductRevenueLine entries, no engine redesign required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ...models.enums import Currency
from ...models.financial_model import ValidationReport
from .projection_period import ProjectionTimeline, YearlySeries


@dataclass
class ProductRevenueLine:
    """Full revenue build-up for one product, across the projection years. Every
    field is a per-year series (or a scalar rate) so no step is hidden."""
    name: str
    installed_capacity: YearlySeries          # rated capacity per year
    capacity_utilisation: YearlySeries        # fraction 0..1 per year
    actual_production: YearlySeries            # capacity × utilisation
    yield_pct: float                           # fraction 0..1 (good-output ratio)
    scrap_pct: float                           # fraction 0..1 (loss ratio)
    saleable_quantity: YearlySeries            # production × yield × (1 − scrap)
    selling_price: YearlySeries                # price per unit per year
    revenue: YearlySeries                      # saleable × price
    capacity_unit: Optional[str] = None

    @property
    def revenue_growth(self) -> List[Optional[float]]:
        return self.revenue.yoy_growth()


@dataclass
class RevenueProjection:
    """Aggregate revenue result: per-product lines + totals + growth + the
    validation summary produced while building it."""
    timeline: ProjectionTimeline
    products: List[ProductRevenueLine] = field(default_factory=list)
    total_saleable_quantity: YearlySeries = field(default_factory=lambda: YearlySeries.zeros(0))
    total_revenue: YearlySeries = field(default_factory=lambda: YearlySeries.zeros(0))
    revenue_growth: List[Optional[float]] = field(default_factory=list)
    currency: Optional[Currency] = None
    validation: ValidationReport = field(default_factory=ValidationReport)

    # -- convenience --------------------------------------------------------
    @property
    def years(self) -> int:
        return self.timeline.years

    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid

    def revenue_year(self, n: int) -> float:
        return self.total_revenue.year(n)

    def product(self, name: str) -> Optional[ProductRevenueLine]:
        for p in self.products:
            if p.name == name:
                return p
        return None

    def summary(self) -> dict:
        """Compact, serialisable snapshot for reporting / debugging."""
        return {
            "years": self.years,
            "currency": self.currency.value if self.currency else None,
            "products": [p.name for p in self.products],
            "total_revenue": self.total_revenue.as_list(),
            "revenue_growth": self.revenue_growth,
            "total_saleable_quantity": self.total_saleable_quantity.as_list(),
            "is_valid": self.is_valid,
            "issues": [
                {"field": i.field, "message": i.message,
                 "severity": i.severity.value, "code": i.code}
                for i in self.validation.issues
            ],
        }
