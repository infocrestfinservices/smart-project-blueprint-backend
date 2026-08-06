"""
provider.py

Chooses how revenue and operating costs are built for a given industry, and returns
the four shapes the generic engine tail consumes. This is the ONLY industry switch
in the calculation path; everything downstream is industry-agnostic.

Manufacturing (and any industry without a dedicated model) uses the original
revenue_calc / expense_calc modules, called exactly as the frozen runner always
called them — so the manufacturing / Bank Loan numbers are byte-for-byte unchanged.
A dedicated industry (retail today) plugs in without touching that path.
"""

from __future__ import annotations

from financial_engine.calculations.generic.revenue_calc import (
    calculate_monthly_production, calculate_monthly_revenue,
)
from financial_engine.calculations.generic.expense_calc import (
    calculate_monthly_variable_costs, calculate_monthly_fixed_costs,
)

def _manufacturing_builder(assumptions: dict) -> dict:
    """Capacity family (goods produced via plant): the original path, verbatim.
    production -> revenue -> var(production) + fix(revenue), exactly as
    financial_engine_runner always assembled them — Bank Loan byte-unchanged."""
    production = calculate_monthly_production(assumptions)
    revenue = calculate_monthly_revenue(assumptions, production)
    var = calculate_monthly_variable_costs(assumptions, production)
    fix = calculate_monthly_fixed_costs(assumptions, revenue)
    return {
        "production": production, "monthly_revenue": revenue,
        "var": var, "fix": fix, "effective_assumptions": assumptions,
    }


def _service_builder(assumptions: dict) -> dict:
    """Volume × price family (retail, restaurant, hotel, software, hospital, …): one
    generic model — revenue = volume × price, cost of sales = revenue × (1 − gross
    margin). The industry's operating_model supplies the driver labels/benchmarks; the
    arithmetic is identical, so every service/trade industry shares this builder."""
    from .retail_calc import build_retail_revenue_and_costs
    return build_retail_revenue_and_costs(assumptions)


def _resolve(industry_type) -> callable:
    from .operating_models import family_of
    return _service_builder if family_of(industry_type) == "volume_price" else _manufacturing_builder


def has_industry_model(industry_type) -> bool:
    """True when a dedicated (non-capacity) model handles this industry."""
    return _resolve(industry_type) is _service_builder


def build_revenue_and_costs(assumptions: dict) -> dict:
    """Dispatch on assumptions['industry_type'] and return
    {production, monthly_revenue, var, fix, effective_assumptions}."""
    builder = _resolve((assumptions or {}).get("industry_type"))
    return builder(assumptions)
