"""
revenue_calc.py

Industry-agnostic revenue calculation. This is a line-for-line Python mirror of the
Bank Loan CMA workbook's **Production** and **Sales** sheets
(templates/bank_loan/CMA_Dashboard_Premium.xlsx), so for the same assumptions dict
the numbers here are IDENTICAL to what Excel recomputes — not merely similar.

The Excel formulas being reproduced:

    Production!<m>6  = (Assumptions!$C$16 * Assumptions!<y>$18 / 12)
                       * IF(SUM(Assumptions!$C$21:$N$21) = 0, 1,
                            12 * Assumptions!<m>$21 / SUM(Assumptions!$C$21:$N$21))

    Sales!<m>6       = Assumptions!$C$23 * (1 + Assumptions!$C$24) ^ <year_index>
    Sales!<m>7       = Sales!<m>5 * Sales!<m>6            (quantity x price)

Mapped to schema field names (assumption_schema.json):

    C16 installed_capacity          C18:G18 capacity_utilisation_y1_y5
    C21:N21 monthly_seasonality_weights
    C23 selling_price_y1            C24 selling_price_escalation

Three behaviours are inherited from Excel deliberately, because deviating would
break numerical parity:

  * Seasonality weights are NORMALISED (12 * w / sum(w)), so only their RATIO
    matters — [1]*12 and [0.5]*12 give identical output. Weights summing to zero
    fall back to a flat multiplier of 1.0 (the IF(...)=0 branch), never a
    division by zero.
  * Escalation is applied per YEAR, flat within the year: year index 0 gets
    (1+esc)^0 = 1, so Year 1 is never escalated.
  * Utilisation is a step function by year, not a monthly ramp.

Pure functions: no I/O, no AI, no Excel, no file access. dict in, list out.
"""

MONTHS_PER_YEAR = 12
YEARS = 5
TOTAL_MONTHS = YEARS * MONTHS_PER_YEAR  # 60

_PRODUCTION_KEYS = (
    "installed_capacity",
    "capacity_utilisation_y1_y5",
    "monthly_seasonality_weights",
)
_REVENUE_KEYS = (
    "selling_price_y1",
    "selling_price_escalation",
)


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


def _series(value, field: str, length: int) -> list:
    """A list-valued assumption (utilisation ramp, seasonality weights), validated
    for length and numeric content."""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field!r} must be a list of {length} values, got {type(value).__name__}")
    if len(value) != length:
        raise ValueError(f"{field!r} must have exactly {length} values, got {len(value)}")
    return [_num(v, f"{field}[{i}]") for i, v in enumerate(value)]


def calculate_monthly_production(assumptions: dict) -> list:
    """60 monthly production-unit values (5 years x 12 months).

    Mirrors Production!row 6:
        (installed_capacity / 12) * utilisation[year] * seasonality_multiplier[month]
    where seasonality_multiplier = 12 * weight[month] / sum(weights), or 1.0 when
    the weights sum to zero.
    """
    _require(assumptions, _PRODUCTION_KEYS, "calculate_monthly_production")

    capacity = _num(assumptions["installed_capacity"], "installed_capacity")
    utilisation = _series(assumptions["capacity_utilisation_y1_y5"],
                          "capacity_utilisation_y1_y5", YEARS)
    weights = _series(assumptions["monthly_seasonality_weights"],
                      "monthly_seasonality_weights", MONTHS_PER_YEAR)

    weight_sum = sum(weights)
    out = []
    for m in range(TOTAL_MONTHS):
        year, month_in_year = divmod(m, MONTHS_PER_YEAR)
        # Excel: IF(SUM(weights)=0, 1, 12*w/SUM(weights))
        season = 1.0 if weight_sum == 0 else (MONTHS_PER_YEAR * weights[month_in_year] / weight_sum)
        out.append((capacity * utilisation[year] / MONTHS_PER_YEAR) * season)
    return out


def calculate_monthly_revenue(assumptions: dict, monthly_production: list) -> list:
    """60 monthly revenue values = production x selling price.

    Mirrors Sales!row 6 (price) and Sales!row 7 (revenue). The price escalates once
    per year: selling_price_y1 * (1 + selling_price_escalation) ** year_index, so
    Year 1 carries the unescalated base price.
    """
    _require(assumptions, _REVENUE_KEYS, "calculate_monthly_revenue")
    if not isinstance(monthly_production, (list, tuple)) or len(monthly_production) != TOTAL_MONTHS:
        raise ValueError(
            f"calculate_monthly_revenue: monthly_production must be a list of "
            f"{TOTAL_MONTHS} values, got "
            f"{len(monthly_production) if isinstance(monthly_production, (list, tuple)) else type(monthly_production).__name__}"
        )

    base_price = _num(assumptions["selling_price_y1"], "selling_price_y1")
    escalation = _num(assumptions["selling_price_escalation"], "selling_price_escalation")

    out = []
    for m, units in enumerate(monthly_production):
        year = m // MONTHS_PER_YEAR
        price = base_price * ((1.0 + escalation) ** year)
        out.append(_num(units, f"monthly_production[{m}]") * price)
    return out


def yearly_totals(monthly: list) -> list:
    """Convenience: collapse a 60-month series into 5 annual totals — the same
    numbers Excel shows in its 'Yr N Total' columns (N, AA, AN, BA, BN)."""
    if not isinstance(monthly, (list, tuple)) or len(monthly) != TOTAL_MONTHS:
        raise ValueError(f"yearly_totals: expected {TOTAL_MONTHS} monthly values")
    return [sum(monthly[y * MONTHS_PER_YEAR:(y + 1) * MONTHS_PER_YEAR]) for y in range(YEARS)]
