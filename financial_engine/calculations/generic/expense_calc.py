"""
expense_calc.py

Industry-agnostic operating-expense calculation. A line-for-line Python mirror of
the Bank Loan CMA workbook's **Expenses** sheet
(templates/bank_loan/CMA_Dashboard_Premium.xlsx), so for the same assumptions dict
the numbers here are IDENTICAL to what Excel recomputes.

The Excel formulas being reproduced (rows 5-12 of Expenses):

    row 5  cost1              = Production!<m>6 * (C25 * (1 + C26) ^ <year>)
    row 6  cost2              = Production!<m>6 * (C27 * (1 + C28) ^ <year>)
    row 8  other variable     = Production!<m>6 * (C29 * (1 + C30) ^ <year>)
    row 7  wages              = C32 * (1 + C33) ^ <year>
    row 9  factory overheads  = C34 * (1 + C35) ^ <year>
    row 10 repairs & maint.   = C36 * (1 + C37) ^ <year>
    row 11 admin expenses     = C38 * (1 + C39) ^ <year>
    row 12 selling & distrib. = Sales!<m>7 * C40          <-- % OF REVENUE, not a flat cost

Two structural facts, straight from the Excel:

  * VARIABLE costs scale with production. Their per-unit rate escalates once a year;
    the monthly figure is that rate x that month's production.
  * PERIOD costs (wages, factory overheads, repairs, admin) are FLAT monthly amounts
    that escalate once a year. They do NOT scale with production.
  * SELLING & DISTRIBUTION is the odd one out: it is a PERCENTAGE of that month's
    revenue (C40 is a decimal fraction, e.g. 0.02 = 2% of sales), so it needs the
    revenue series, and it does not escalate — it tracks revenue automatically.

Note this sheet also carries depreciation (row 13) and interest (rows 14-15). Those
are NOT operating-cost inputs — they are derived from the loan and asset schedules —
so they belong to their own calculators, not here.

Pure functions: no I/O, no AI, no Excel, no file access. dict in, dict of lists out.
"""

MONTHS_PER_YEAR = 12
YEARS = 5
TOTAL_MONTHS = YEARS * MONTHS_PER_YEAR  # 60

# variable cost line -> (per-unit rate field, its escalation field)
_VARIABLE_COSTS = {
    "cost1": ("cost1_per_unit_y1", "cost1_escalation"),
    "cost2": ("cost2_per_unit_y1", "cost2_escalation"),
    "other_variable": ("other_variable_cost_y1", "other_variable_escalation"),
}

# flat monthly period cost -> (monthly amount field, its escalation field)
_PERIOD_COSTS = {
    "wages": ("wages_monthly_y1", "wages_escalation"),
    "factory_overheads": ("factory_overheads_monthly_y1", "factory_oh_escalation"),
    "repairs_maintenance": ("repairs_maintenance_monthly_y1", "rm_escalation"),
    "admin_expenses": ("admin_expenses_monthly_y1", "admin_escalation"),
}

# selling & distribution is a share of revenue, not an escalating flat cost
_REVENUE_LINKED = "selling_distribution"


def _require(assumptions: dict, keys, fn_name: str) -> None:
    """Fail loudly and early. A missing key must never become a silent 0 that
    propagates through the whole model as a plausible-looking wrong number."""
    if not isinstance(assumptions, dict):
        raise ValueError(f"{fn_name}: assumptions must be a dict, got {type(assumptions).__name__}")
    missing = [k for k in keys if assumptions.get(k) is None]
    if missing:
        raise ValueError(
            f"{fn_name}: missing required assumption field(s): {', '.join(missing)}. "
            f"These must be present in the assumptions dict (see assumption_schema.json)."
        )


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def _check_series(series, name: str, fn_name: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != TOTAL_MONTHS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn_name}: {name} must be a list of {TOTAL_MONTHS} values, got {got}")
    return [_num(v, f"{name}[{i}]") for i, v in enumerate(series)]


def calculate_monthly_variable_costs(assumptions: dict, monthly_production: list) -> dict:
    """{"cost1": [...60...], "cost2": [...60...], "other_variable": [...60...]}

    Each month = that month's production x the per-unit rate for that year, where the
    rate = base_rate * (1 + its own escalation) ** year_index. Mirrors Expenses rows
    5, 6 and 8.
    """
    keys = [f for pair in _VARIABLE_COSTS.values() for f in pair]
    _require(assumptions, keys, "calculate_monthly_variable_costs")
    production = _check_series(monthly_production, "monthly_production",
                               "calculate_monthly_variable_costs")

    out = {}
    for line, (rate_field, esc_field) in _VARIABLE_COSTS.items():
        base = _num(assumptions[rate_field], rate_field)
        esc = _num(assumptions[esc_field], esc_field)
        series = []
        for m, units in enumerate(production):
            year = m // MONTHS_PER_YEAR
            rate = base * ((1.0 + esc) ** year)
            series.append(units * rate)
        out[line] = series
    return out


def calculate_monthly_fixed_costs(assumptions: dict, monthly_revenue: list = None) -> dict:
    """{"wages", "factory_overheads", "repairs_maintenance", "admin_expenses",
        "selling_distribution"} -> 60 monthly values each.

    wages / factory_overheads / repairs_maintenance / admin_expenses are flat monthly
    figures escalated once a year (Expenses rows 7, 9, 10, 11).

    selling_distribution is NOT a flat escalating cost: it is a percentage of that
    month's revenue (Expenses row 12 = Sales!revenue * C40). `monthly_revenue` is
    therefore required to compute it — call calculate_monthly_revenue() first and pass
    the result. Omitting it raises rather than silently returning a zero line.
    """
    keys = [f for pair in _PERIOD_COSTS.values() for f in pair] + [_REVENUE_LINKED]
    _require(assumptions, keys, "calculate_monthly_fixed_costs")

    if monthly_revenue is None:
        raise ValueError(
            "calculate_monthly_fixed_costs: monthly_revenue is required because "
            "selling_distribution is a PERCENTAGE OF REVENUE (Expenses!row12 = "
            "Sales!revenue * selling_distribution), not a flat monthly cost. "
            "Call calculate_monthly_revenue() first and pass its result."
        )
    revenue = _check_series(monthly_revenue, "monthly_revenue", "calculate_monthly_fixed_costs")

    out = {}
    for line, (amount_field, esc_field) in _PERIOD_COSTS.items():
        base = _num(assumptions[amount_field], amount_field)
        esc = _num(assumptions[esc_field], esc_field)
        out[line] = [base * ((1.0 + esc) ** (m // MONTHS_PER_YEAR)) for m in range(TOTAL_MONTHS)]

    sd_rate = _num(assumptions[_REVENUE_LINKED], _REVENUE_LINKED)
    out[_REVENUE_LINKED] = [rev * sd_rate for rev in revenue]
    return out


def yearly_totals(monthly: list) -> list:
    """Collapse a 60-month series into 5 annual totals — the same numbers Excel shows
    in its 'Yr N Total' columns."""
    if not isinstance(monthly, (list, tuple)) or len(monthly) != TOTAL_MONTHS:
        raise ValueError(f"yearly_totals: expected {TOTAL_MONTHS} monthly values")
    return [sum(monthly[y * MONTHS_PER_YEAR:(y + 1) * MONTHS_PER_YEAR]) for y in range(YEARS)]
