"""
profit_calc.py

Industry-agnostic P&L: EBITDA -> EBIT -> PBT -> PAT -> Cash Accrual. A line-for-line
mirror of the Bank Loan CMA workbook's **Profit** sheet.

The Excel formulas being reproduced (<m> = that month's column):

    r5   Net Sales                   = Sales!<m>7
    r6   (-) cost1                   = Expenses!<m>5
    r7   (-) cost2                   = Expenses!<m>6
    r8   (-) Direct wages            = Expenses!<m>7
    r9   (-) Other variable cost     = Expenses!<m>8
    r10  (-) Factory overheads       = Expenses!<m>9
    r11  (-) Repairs & maintenance   = Expenses!<m>10
    r12  (-) Administrative expenses = Expenses!<m>11
    r13  (-) Selling & distribution  = Expenses!<m>12

    r14  EBITDA                      = <m>5 - SUM(<m>6:<m>13)
    r15  (-) Depreciation            = Expenses!<m>13
    r16  EBIT                        = <m>14 - <m>15
    r17  (-) Interest - Term Loan    = Expenses!<m>14
    r18  (-) Interest - Working Cap. = Expenses!<m>15
    r19  PBT                         = <m>16 - <m>17 - <m>18
    r20  (-) Income Tax  [MONTHLY]   = IF(<m>19 > 0, <m>19 * Assumptions!$C$14, 0)
    r21  PAT             [MONTHLY]   = <m>19 - <m>20
    r22  Cash Accrual    [MONTHLY]   = <m>21 + <m>15        (PAT + depreciation)

ANNUAL TAX — tax on the ANNUAL PBT total (the CORRECTED formula)
---------------------------------------------------------------
This module mirrors the annual-total columns (N, AA, AN, BA, BN), which were patched
in the template to compute tax on the YEAR's PBT rather than by summing 12 monthly
IF-tests. The corrected annual formulas are:

    r20  Income Tax   = IF(<annual PBT> > 0, <annual PBT> * Assumptions!$C$14, 0)
    r21  PAT          = <annual PBT> - <annual tax>
    r22  Cash Accrual = <annual PAT> + <annual depreciation>

So this module computes annual tax as `income_tax_rate * annual_pbt if annual_pbt > 0
else 0` — NOT as the sum of the 12 monthly IF(monthly_pbt>0, ...) charges. The monthly
income-tax series is still returned under "monthly_income_tax" for month-level detail
views (mirroring the untouched monthly cells B20:M20), but it is NOT what the annual
income_tax figure is built from.

WHY THIS CHANGED (the monthly-sum bug it replaces)
--------------------------------------------------
The old approach summed 12 monthly IF-tests. Because each month's tax is floored at
zero, a loss-making month contributed 0 tax but no relief against the profitable
months — so a business with a loss month inside an otherwise-profitable year was
OVERCHARGED. This was found with the Tourism & Hospitality test case: a hill-station
hotel with a 2-month off-season posted a profitable year (PBT ~26.2 lakh) but 2 of 12
months lost money, and the monthly-sum tax came to 28.33% of annual PBT at a 25% rate
— a ~13% (~87k) overcharge in Year 1. Computing tax on the annual PBT total removes
this: profits and losses within the year net off first, then tax applies once.

Still NOT modelled (a separate, larger change, deliberately out of scope here):
NO LOSS CARRY-FORWARD ACROSS YEARS. A whole loss-making YEAR still shelters nothing in
later years; Indian law allows an 8-year carry-forward. This fix only nets months
WITHIN a year, matching the corrected Excel.

Mapped to schema field names (assumption_schema.json):

    C14 income_tax_rate

Pure functions: no I/O, no AI, no Excel, no file access.
"""

MONTHS_PER_YEAR = 12
YEARS = 5
TOTAL_MONTHS = YEARS * MONTHS_PER_YEAR  # 60

_REQUIRED_KEYS = ("income_tax_rate",)

# Profit rows 6-13: the eight operating cost lines deducted to reach EBITDA.
# Depreciation and both interest lines are deliberately absent.
_EBITDA_VARIABLE_LINES = ("cost1", "cost2", "other_variable")
_EBITDA_FIXED_LINES = ("wages", "factory_overheads", "repairs_maintenance",
                       "admin_expenses", "selling_distribution")


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


def _monthly(series, name: str, fn: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != TOTAL_MONTHS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn}: {name} must be a list of {TOTAL_MONTHS} monthly values, got {got}")
    return [_num(v, f"{name}[{i}]") for i, v in enumerate(series)]


def _annual(series, name: str, fn: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != YEARS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn}: {name} must be a list of {YEARS} annual values, got {got}")
    return [_num(v, f"{name}[{i}]") for i, v in enumerate(series)]


def _cost_lines(costs: dict, names, label: str, fn: str) -> dict:
    if not isinstance(costs, dict):
        raise ValueError(f"{fn}: {label} must be a dict, got {type(costs).__name__}")
    missing = [n for n in names if n not in costs]
    if missing:
        raise ValueError(f"{fn}: {label} is missing cost line(s): {', '.join(missing)}")
    return {n: _monthly(costs[n], f"{label}['{n}']", fn) for n in names}


def _yearly(monthly: list) -> list:
    return [sum(monthly[y * MONTHS_PER_YEAR:(y + 1) * MONTHS_PER_YEAR]) for y in range(YEARS)]


def calculate_profit_and_loss(
    assumptions: dict,
    monthly_revenue: list,
    monthly_variable_costs: dict,
    monthly_fixed_costs: dict,
    monthly_depreciation: float,
    loan_interest_annual: list,
    wc_interest_annual: list,
) -> dict:
    """Mirrors the Profit sheet exactly.

    Returns {"ebitda", "ebit", "pbt", "income_tax", "pat", "cash_accrual"} — each a
    list of 5 ANNUAL values — plus the underlying 60-month series under
    "monthly_<name>" so callers can inspect the month-level detail the annual figures
    are summed from (which is where the tax quirk lives).

    Args:
        monthly_depreciation: the FLAT monthly charge (a scalar) — the workbook's
            depreciation is identical in every month.
        loan_interest_annual / wc_interest_annual: 5 ANNUAL figures. The workbook
            spreads each year's interest flat across its 12 months (Expenses r14/r15
            are `<annual>/12`), so that is what happens here.
    """
    fn = "calculate_profit_and_loss"
    _require(assumptions, _REQUIRED_KEYS, fn)

    tax_rate = _num(assumptions["income_tax_rate"], "income_tax_rate")
    revenue = _monthly(monthly_revenue, "monthly_revenue", fn)
    var = _cost_lines(monthly_variable_costs, _EBITDA_VARIABLE_LINES, "monthly_variable_costs", fn)
    fix = _cost_lines(monthly_fixed_costs, _EBITDA_FIXED_LINES, "monthly_fixed_costs", fn)
    dep_m = _num(monthly_depreciation, "monthly_depreciation")
    tl_annual = _annual(loan_interest_annual, "loan_interest_annual", fn)
    wc_annual = _annual(wc_interest_annual, "wc_interest_annual", fn)

    # Expenses r14 / r15: each year's interest spread flat over its 12 months.
    tl_m = [tl_annual[m // MONTHS_PER_YEAR] / MONTHS_PER_YEAR for m in range(TOTAL_MONTHS)]
    wc_m = [wc_annual[m // MONTHS_PER_YEAR] / MONTHS_PER_YEAR for m in range(TOTAL_MONTHS)]

    ebitda, ebit, pbt = [], [], []
    monthly_tax, monthly_pat, monthly_accrual = [], [], []
    for m in range(TOTAL_MONTHS):
        # r14: Net Sales less the eight operating cost lines (rows 6-13).
        operating = sum(var[n][m] for n in _EBITDA_VARIABLE_LINES) \
            + sum(fix[n][m] for n in _EBITDA_FIXED_LINES)
        e = revenue[m] - operating
        b = e - dep_m                                   # r16 EBIT = EBITDA - depreciation
        p = b - tl_m[m] - wc_m[m]                       # r19 PBT = EBIT - TL int - WC int
        ebitda.append(e); ebit.append(b); pbt.append(p)
        # Monthly tax/PAT are retained ONLY for month-level detail (the untouched
        # monthly cells B20:M20). The ANNUAL figures below do NOT sum these.
        mt = p * tax_rate if p > 0 else 0.0             # monthly IF(PBT>0, PBT*rate, 0)
        monthly_tax.append(mt)
        monthly_pat.append(p - mt)
        monthly_accrual.append((p - mt) + dep_m)

    annual_ebitda = _yearly(ebitda)
    annual_ebit = _yearly(ebit)
    annual_pbt = _yearly(pbt)
    # r20 (corrected): tax on the ANNUAL PBT total, not the sum of monthly IF-tests.
    annual_tax = [p * tax_rate if p > 0 else 0.0 for p in annual_pbt]
    # r21: PAT = annual PBT - annual tax.  r22: Cash Accrual = annual PAT + annual dep.
    annual_pat = [p - t for p, t in zip(annual_pbt, annual_tax)]
    annual_dep = dep_m * MONTHS_PER_YEAR
    annual_accrual = [pat_ + annual_dep for pat_ in annual_pat]

    return {
        "ebitda": annual_ebitda,
        "ebit": annual_ebit,
        "pbt": annual_pbt,
        "income_tax": annual_tax,
        "pat": annual_pat,
        "cash_accrual": annual_accrual,
        "monthly_ebitda": ebitda,
        "monthly_ebit": ebit,
        "monthly_pbt": pbt,
        "monthly_income_tax": monthly_tax,
        "monthly_pat": monthly_pat,
        "monthly_cash_accrual": monthly_accrual,
    }
