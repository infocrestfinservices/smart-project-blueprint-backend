"""
financial_engine.industry_calc

Per-industry revenue & cost construction. Everything downstream of revenue and
operating costs — depreciation, loan schedule, working capital, P&L, cash flow,
IRR/NPV, balance sheet, ratios — is genuinely industry-agnostic and is REUSED
verbatim. Only two things vary by industry and live here:

  1. how many UNITS are sold and at what price (the revenue driver), and
  2. how the OPERATING COST lines are built (a factory's raw-material-per-unit vs
     a retailer's cost of goods sold via gross margin).

Each industry module returns the exact shapes the generic engine tail already
consumes — monthly production (units), monthly revenue, a `var` cost dict and a
`fix` cost dict — plus an "effective assumptions" view that maps the industry's
own concepts onto the engine's existing computational slots (e.g. a retailer's
stock-cover days onto the raw-material-holding slot the working-capital module
reads). Manufacturing keeps using the original calc modules unchanged; new
industries plug in here without touching the frozen manufacturing path.
"""

from .provider import build_revenue_and_costs, has_industry_model

__all__ = ["build_revenue_and_costs", "has_industry_model"]
