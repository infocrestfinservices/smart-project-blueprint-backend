"""
retail_calc.py

Retail & E-Commerce revenue and operating-cost construction.

A retailer is not a factory, and this is where that stops being cosmetic. The
manufacturing engine builds revenue from installed capacity x utilisation and cost
from raw-material-per-unit; neither exists in retail. Here:

  * REVENUE is units sold x average selling price (ASP). Volume is a direct annual
    units figure per year (a retailer forecasts sales, not machine output), spread
    across months by the same seasonality weights the rest of the engine uses.
  * COST OF GOODS SOLD is the purchase price of inventory, derived from gross
    margin: COGS = revenue x (1 - gross_margin). This is the retailer's single
    largest cost — and it has no home at all in the manufacturing vocabulary, which
    is exactly why every earlier "retail" report was really a factory.
  * FACTORY OVERHEADS and PLANT & MACHINERY do not exist and are zero.

Everything the retailer DOES share with the generic engine — wages, admin,
repairs, selling & distribution, the loan, tax, depreciation of building/furniture,
working capital, ratios — is reused unchanged. This module only produces the four
shapes the generic tail consumes (production units, monthly revenue, `var`, `fix`)
plus an effective-assumptions view that maps retail concepts onto the engine's
existing slots.

Retail-native input fields (beyond the shared engine vocabulary):
    annual_units_sold_y1_y5   list[5]  units sold each year (Year 1..5)
    gross_margin_pct          fraction (revenue - COGS) / revenue

Reused engine fields (present in the retail profile as `applies:true`):
    selling_price_y1, selling_price_escalation, monthly_seasonality_weights,
    other_variable_cost_y1, other_variable_escalation,
    wages_monthly_y1, wages_escalation, repairs_maintenance_monthly_y1, rm_escalation,
    admin_expenses_monthly_y1, admin_escalation, selling_distribution,
    inventory_holding_days (stock cover), receivables_days, payables_days, ...

Pure functions: dict in, lists/dicts out. No I/O, no AI, no Excel.
"""

from __future__ import annotations

from financial_engine.calculations.generic.expense_calc import calculate_monthly_fixed_costs
from financial_engine.calculations.generic.revenue_calc import (
    MONTHS_PER_YEAR, TOTAL_MONTHS, YEARS,
)

# Manufacturing fields that a retailer does not have. Forced to 0 so the generic
# tail (which requires them present) computes a true zero rather than crashing, and
# so no factory line ever appears in a retail report.
_ZEROED_FOR_RETAIL = (
    "installed_capacity", "plant_machinery_cost", "plant_machinery_dep_rate",
    "cost1_per_unit_y1", "cost1_escalation", "cost2_per_unit_y1", "cost2_escalation",
    "factory_overheads_monthly_y1", "factory_oh_escalation",
    "finished_goods_holding_days",
)

_REQUIRED = (
    "annual_units_sold_y1_y5", "gross_margin_pct",
    "selling_price_y1", "selling_price_escalation", "monthly_seasonality_weights",
)


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def _series(value, field: str, length: int) -> list:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field!r} must be a list of {length} values, got {type(value).__name__}")
    if len(value) != length:
        raise ValueError(f"{field!r} must have exactly {length} values, got {len(value)}")
    return [_num(v, f"{field}[{i}]") for i, v in enumerate(value)]


def _require(assumptions: dict) -> None:
    if not isinstance(assumptions, dict):
        raise ValueError(f"retail_calc: assumptions must be a dict, got {type(assumptions).__name__}")
    missing = [k for k in _REQUIRED if assumptions.get(k) is None]
    if missing:
        raise ValueError(
            f"retail_calc: missing required retail assumption field(s): {', '.join(missing)}. "
            f"Retail revenue needs annual units, ASP and gross margin.")


def _monthly_units(assumptions: dict) -> list:
    """60 monthly unit-sales values. annual_units_sold[year] spread across the 12
    months by the same normalised seasonality weights the manufacturing engine uses
    (12 * w / sum(w); flat 1.0 when weights sum to zero), so Diwali/festive peaks
    are modelled the same way — only the annual volume source differs."""
    annual_units = _series(assumptions["annual_units_sold_y1_y5"], "annual_units_sold_y1_y5", YEARS)
    weights = _series(assumptions["monthly_seasonality_weights"],
                      "monthly_seasonality_weights", MONTHS_PER_YEAR)
    weight_sum = sum(weights)
    out = []
    for m in range(TOTAL_MONTHS):
        year, month_in_year = divmod(m, MONTHS_PER_YEAR)
        season = 1.0 if weight_sum == 0 else (MONTHS_PER_YEAR * weights[month_in_year] / weight_sum)
        out.append((annual_units[year] / MONTHS_PER_YEAR) * season)
    return out


def _monthly_revenue(assumptions: dict, monthly_units: list) -> list:
    """units x ASP, ASP escalated once per year (Year 1 unescalated), matching the
    engine's per-year escalation convention."""
    base_price = _num(assumptions["selling_price_y1"], "selling_price_y1")
    esc = _num(assumptions["selling_price_escalation"], "selling_price_escalation")
    out = []
    for m, units in enumerate(monthly_units):
        year = m // MONTHS_PER_YEAR
        out.append(units * base_price * ((1.0 + esc) ** year))
    return out


def _monthly_variable_costs(assumptions: dict, monthly_units: list, monthly_revenue: list) -> dict:
    """Retail variable costs in the engine's `var` shape.

      cost1          = COGS = revenue x (1 - gross_margin)   (inventory purchase cost)
      cost2          = 0                                     (no second production input)
      other_variable = units x per-unit rate (payment gateway, packaging), escalated
    """
    gm = _num(assumptions["gross_margin_pct"], "gross_margin_pct")
    ov_base = _num(assumptions.get("other_variable_cost_y1") or 0.0, "other_variable_cost_y1")
    ov_esc = _num(assumptions.get("other_variable_escalation") or 0.0, "other_variable_escalation")

    cost1, cost2, other = [], [], []
    for m in range(TOTAL_MONTHS):
        year = m // MONTHS_PER_YEAR
        cost1.append(monthly_revenue[m] * (1.0 - gm))
        cost2.append(0.0)
        other.append(monthly_units[m] * ov_base * ((1.0 + ov_esc) ** year))
    return {"cost1": cost1, "cost2": cost2, "other_variable": other}


def _effective_assumptions(assumptions: dict) -> dict:
    """A view of the assumptions the generic tail can consume directly:
      * factory / plant / raw-material fields forced to 0 (retail has none), so the
        modules that require them present compute a genuine zero;
      * retail stock-cover days mapped onto the working-capital module's raw-material
        holding slot (that module applies rm_days to `annual_purchases`, which the
        runner feeds as COGS — so this yields retail inventory = days x COGS/365);
        finished-goods holding set to 0.
    The original dict is never mutated.
    """
    eff = dict(assumptions)
    for k in _ZEROED_FOR_RETAIL:
        eff[k] = 0
    inv_days = assumptions.get("inventory_holding_days")
    if inv_days is not None:
        eff["raw_material_holding_days"] = inv_days
    eff.setdefault("raw_material_holding_days", 0)
    return eff


def build_retail_revenue_and_costs(assumptions: dict) -> dict:
    """Return {production, monthly_revenue, var, fix, effective_assumptions} for a
    retail business, in the exact shapes the generic engine tail consumes."""
    _require(assumptions)
    eff = _effective_assumptions(assumptions)

    units = _monthly_units(assumptions)
    revenue = _monthly_revenue(assumptions, units)
    var = _monthly_variable_costs(assumptions, units, revenue)

    # Fixed costs reuse the generic formula (wages/repairs/admin/selling escalated
    # yearly; selling & distribution as % of revenue). factory_overheads comes back
    # zero because eff zeroed its base — no retail factory line.
    fix = calculate_monthly_fixed_costs(eff, revenue)

    return {
        "production": units,          # "units" is the generic tail's volume signal
        "monthly_revenue": revenue,
        "var": var,
        "fix": fix,
        "effective_assumptions": eff,
    }
