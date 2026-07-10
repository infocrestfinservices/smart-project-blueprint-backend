"""
revenue_engine.py

The Manufacturing Revenue Engine — the first real deterministic calculation
module of the Financial Engine.

    BusinessProfile + ManufacturingModel + Assumptions
        → RevenueProjection
        → FinancialModel.revenue

It follows professional manufacturing revenue logic as discrete, auditable steps:

    installed capacity
        → capacity utilisation (ramped by year, from assumptions)
        → actual production            (capacity × utilisation)
        → yield adjustment             (× yield %)
        → less production loss / scrap  (× (1 − scrap %))
        → saleable quantity
        → selling price (escalated)
        → revenue                       (saleable × price)

No Excel, no Word, no AI, no randomness — same inputs always yield the same
RevenueProjection. It populates ONLY FinancialModel.revenue and leaves every
other section untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ...industry_models.manufacturing import ManufacturingModel
from ...models.assumptions import Assumptions
from ...models.business_profile import BusinessProfile
from ...models.enums import Industry
from ...models.financial_model import FinancialModel, ValidationReport
from .projection_period import ProjectionTimeline, YearlySeries
from .revenue_projection import ProductRevenueLine, RevenueProjection
from .revenue_validator import RevenueValidator


# ── helpers ─────────────────────────────────────────────────────────────────
def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _rate(v, default: float = 0.0) -> float:
    """Read a value that may be a percent (60) or a fraction (0.6) → fraction."""
    if v is None:
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):
        return default
    return x / 100.0 if x > 1 else x


@dataclass
class _ProductInput:
    """Normalised per-product inputs the engine works from."""
    name: str
    installed_capacity: Optional[float]
    selling_price: Optional[float]
    capacity_unit: Optional[str] = None
    price_growth_override: Optional[float] = None


class ManufacturingRevenueEngine:
    """Deterministic revenue projection for manufacturing businesses."""

    industry = Industry.MANUFACTURING

    DEFAULT_YEARS = 5
    DEFAULT_UTILISATION = 0.60
    DEFAULT_YIELD = 1.0
    DEFAULT_SCRAP = 0.0

    def __init__(self, validator: Optional[RevenueValidator] = None) -> None:
        self.validator = validator or RevenueValidator()

    # -- public API ---------------------------------------------------------
    def project(self, profile: BusinessProfile, industry_model: ManufacturingModel,
                assumptions: Optional[Assumptions] = None) -> RevenueProjection:
        """Pure calculation: returns a RevenueProjection, no side effects."""
        assumptions = assumptions or industry_model.default_assumptions()
        timeline = self._build_timeline(profile, assumptions)
        n = timeline.years

        util_default = self._utilisation_series(profile, assumptions, industry_model, n)
        yield_pct = _rate(self._extra(assumptions, "yield_pct"), self.DEFAULT_YIELD)
        scrap_pct = _rate(self._extra(assumptions, "scrap_pct"), self.DEFAULT_SCRAP)
        price_growth = self._price_growth(assumptions)

        report = ValidationReport()
        products: List[ProductRevenueLine] = []
        for pin in self._resolve_products(profile, industry_model):
            # 1. Validate this product's inputs (never fail silently).
            self.validator.validate_inputs(
                product_name=pin.name,
                installed_capacity=pin.installed_capacity,
                selling_price=pin.selling_price,
                utilisation=util_default,
                yield_pct=yield_pct,
                scrap_pct=scrap_pct,
                report=report,
            )
            products.append(self._build_product_line(
                pin, timeline, util_default, yield_pct, scrap_pct, price_growth))

        total_saleable = YearlySeries.sum((p.saleable_quantity for p in products), n)
        total_revenue = YearlySeries.sum((p.revenue for p in products), n)

        projection = RevenueProjection(
            timeline=timeline,
            products=products,
            total_saleable_quantity=total_saleable,
            total_revenue=total_revenue,
            revenue_growth=total_revenue.yoy_growth(),
            currency=profile.currency,
            validation=report,
        )
        # 2. Post-calculation consistency checks.
        self.validator.validate_projection(projection, report)
        return projection

    def populate(self, financial_model: FinancialModel, projection: RevenueProjection) -> None:
        """Store the projection into FinancialModel.revenue (and nothing else)."""
        section = financial_model.revenue
        section.is_populated = True
        section.data["projection"] = projection
        section.data["total_revenue"] = projection.total_revenue.as_list()
        section.data["revenue_growth"] = projection.revenue_growth
        section.data["validation"] = projection.validation

    def run(self, profile: BusinessProfile, industry_model: ManufacturingModel,
            financial_model: FinancialModel,
            assumptions: Optional[Assumptions] = None) -> RevenueProjection:
        """project() + populate() — the end-to-end entry point."""
        projection = self.project(profile, industry_model, assumptions)
        self.populate(financial_model, projection)
        return projection

    # -- per-product build (each manufacturing step is its own method) ------
    def _build_product_line(self, pin: _ProductInput, timeline: ProjectionTimeline,
                            utilisation: YearlySeries, yield_pct: float, scrap_pct: float,
                            price_growth: float) -> ProductRevenueLine:
        n = timeline.years
        capacity = YearlySeries.constant(_num(pin.installed_capacity), n)          # installed capacity
        production = self._actual_production(capacity, utilisation)                 # capacity × utilisation
        yielded = self._apply_yield(production, yield_pct)                          # yield adjustment
        saleable = self._apply_scrap(yielded, scrap_pct)                           # less scrap
        growth = pin.price_growth_override if pin.price_growth_override is not None else price_growth
        price = self._price_series(_num(pin.selling_price), growth, n)              # selling price
        revenue = self._revenue(saleable, price)                                    # revenue

        return ProductRevenueLine(
            name=pin.name,
            installed_capacity=capacity,
            capacity_utilisation=utilisation,
            actual_production=production,
            yield_pct=yield_pct,
            scrap_pct=scrap_pct,
            saleable_quantity=saleable,
            selling_price=price,
            revenue=revenue,
            capacity_unit=pin.capacity_unit,
        )

    @staticmethod
    def _actual_production(capacity: YearlySeries, utilisation: YearlySeries) -> YearlySeries:
        return capacity.multiply(utilisation)

    @staticmethod
    def _apply_yield(production: YearlySeries, yield_pct: float) -> YearlySeries:
        return production.scale(yield_pct)

    @staticmethod
    def _apply_scrap(yielded: YearlySeries, scrap_pct: float) -> YearlySeries:
        return yielded.scale(1.0 - scrap_pct)

    @staticmethod
    def _price_series(base_price: float, growth: float, n: int) -> YearlySeries:
        return YearlySeries([base_price * ((1.0 + growth) ** i) for i in range(n)])

    @staticmethod
    def _revenue(saleable: YearlySeries, price: YearlySeries) -> YearlySeries:
        return saleable.multiply(price)

    # -- input resolution ---------------------------------------------------
    def _build_timeline(self, profile: BusinessProfile, assumptions: Assumptions) -> ProjectionTimeline:
        years = (assumptions.macro.projection_years
                 or profile.timeline.projection_years
                 or self.DEFAULT_YEARS)
        return ProjectionTimeline.of_years(int(years), profile.timeline.start_year)

    def _utilisation_series(self, profile: BusinessProfile, assumptions: Assumptions,
                            model: ManufacturingModel, n: int) -> YearlySeries:
        """Utilisation ramp — user plan first, then assumptions, then the model
        benchmark. Growth comes from data, not a hardcoded curve."""
        source = (profile.operations.capacity_utilisation_by_year
                  or assumptions.revenue.ramp_by_year
                  or {})
        if source:
            mapping = {int(k): _rate(v) for k, v in source.items()}
            return YearlySeries.from_mapping(mapping, n, default=self.DEFAULT_UTILISATION, hold_last=True)
        driver = model.get_driver("capacity_utilisation")
        base = _rate(driver.benchmark) if driver and driver.benchmark is not None else self.DEFAULT_UTILISATION
        return YearlySeries.constant(base, n)

    def _price_growth(self, assumptions: Assumptions) -> float:
        return _rate(assumptions.macro.inflation_pct, 0.0)

    def _resolve_products(self, profile: BusinessProfile,
                          model: ManufacturingModel) -> List[_ProductInput]:
        """Normalise the profile into one or more products. Multi-product ready:
        production.product_lines drive it; sales.products supply prices."""
        sales = profile.sales.products
        lines = profile.production.product_lines

        if lines:
            out: List[_ProductInput] = []
            for i, pl in enumerate(lines):
                name = pl.name or f"Product {chr(65 + i)}"
                cap = pl.installed_capacity if pl.installed_capacity is not None else profile.production.installed_capacity
                price, growth = self._price_for(name, i, sales)
                out.append(_ProductInput(name, cap, price,
                                         pl.capacity_unit or profile.production.capacity_unit, growth))
            return out

        if sales:
            out = []
            for i, sp in enumerate(sales):
                name = sp.name or f"Product {chr(65 + i)}"
                cap = (profile.production.installed_capacity
                       if profile.production.installed_capacity is not None else sp.year1_volume)
                growth = _rate(sp.annual_growth_pct) if sp.annual_growth_pct is not None else None
                out.append(_ProductInput(name, cap, sp.unit_selling_price,
                                         profile.production.capacity_unit, growth))
            return out

        # Single synthesised product from top-level facts (price likely absent →
        # will be flagged by validation rather than silently producing 0).
        name = profile.project.title or "Product A"
        return [_ProductInput(name, profile.production.installed_capacity, None,
                              profile.production.capacity_unit, None)]

    @staticmethod
    def _price_for(name: str, index: int, sales) -> tuple:
        """Match a sales product to a production line by name, then by index,
        then fall back to the first sales price. Returns (price, growth)."""
        if not sales:
            return None, None
        by_name = next((s for s in sales if (s.name or "").strip().lower() == name.strip().lower()), None)
        chosen = by_name or (sales[index] if index < len(sales) else sales[0])
        growth = _rate(chosen.annual_growth_pct) if chosen.annual_growth_pct is not None else None
        return chosen.unit_selling_price, growth

    @staticmethod
    def _extra(assumptions: Assumptions, key: str):
        return assumptions.extra.get(key)
