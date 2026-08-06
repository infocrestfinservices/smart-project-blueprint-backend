"""
depreciation_calc.py

Industry-agnostic depreciation. A line-for-line mirror of the Bank Loan CMA
workbook's depreciation line, Expenses!row 13:

    Expenses!<m>13 = (Assumptions!$C$43 * Assumptions!$C$44
                      + Assumptions!$C$45 * Assumptions!$C$46
                      + Assumptions!$C$47 * Assumptions!$C$48) / 12

Mapped to schema field names (assumption_schema.json):

    C43 building_cost          x  C44 building_dep_rate
    C45 plant_machinery_cost   x  C46 plant_machinery_dep_rate
    C47 furniture_other_cost   x  C48 furniture_dep_rate

Two facts verified directly against the workbook, both deliberately reproduced:

  * STRAIGHT-LINE and FLAT. The formula is byte-identical in all 60 monthly
    columns (B13, C13, O13, AB13, AO13, BB13 all match), so depreciation does not
    change year to year. No written-down-value, no reducing balance, no asset
    retirement.
  * LAND IS NOT DEPRECIATED. land_cost (C42) is absent from the formula, which is
    correct accounting — land does not depreciate.

Pure functions: no I/O, no AI, no Excel, no file access.
"""

MONTHS_PER_YEAR = 12
YEARS = 5
TOTAL_MONTHS = YEARS * MONTHS_PER_YEAR  # 60

# (cost field, depreciation-rate field) — land is deliberately absent.
_DEPRECIABLE_BLOCKS = (
    ("building_cost", "building_dep_rate"),
    ("plant_machinery_cost", "plant_machinery_dep_rate"),
    ("furniture_other_cost", "furniture_dep_rate"),
)

_REQUIRED_KEYS = tuple(f for pair in _DEPRECIABLE_BLOCKS for f in pair)


def _require(assumptions: dict, keys, fn_name: str) -> None:
    """Fail loudly and early. A missing key must never become a silent 0 that
    propagates through the model as a plausible-looking wrong number."""
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


def calculate_annual_depreciation(assumptions: dict) -> float:
    """Total depreciation for one year: sum of (block cost x block rate) over the
    three depreciable blocks. This is the numerator of Expenses!row 13."""
    _require(assumptions, _REQUIRED_KEYS, "calculate_annual_depreciation")
    return sum(
        _num(assumptions[cost], cost) * _num(assumptions[rate], rate)
        for cost, rate in _DEPRECIABLE_BLOCKS
    )


def calculate_monthly_depreciation(assumptions: dict) -> float:
    """The flat monthly depreciation charge — identical in every one of the 60
    months, exactly as Expenses!row 13 computes it."""
    _require(assumptions, _REQUIRED_KEYS, "calculate_monthly_depreciation")
    return calculate_annual_depreciation(assumptions) / MONTHS_PER_YEAR


def monthly_depreciation_series(assumptions: dict) -> list:
    """The same flat charge repeated across all 60 months, for callers that want a
    series aligned with the other monthly cost lines."""
    return [calculate_monthly_depreciation(assumptions)] * TOTAL_MONTHS


def annual_depreciation_series(assumptions: dict) -> list:
    """The annual charge repeated across all 5 years."""
    return [calculate_annual_depreciation(assumptions)] * YEARS
