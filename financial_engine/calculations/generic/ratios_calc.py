"""
ratios_calc.py

Industry-agnostic financial ratios. A line-for-line mirror of the Bank Loan CMA
workbook's **Ratios** sheet, plus the **DSCR** sheet (which Ratios!r15 just passes
through, and whose per-year and average values this module computes directly).

The Excel formulas being reproduced (columns C..G = Years 1..5; every ratio is
wrapped in IFERROR(..., 0) so a zero denominator yields 0, not an error):

    Ratios r6  Current Ratio      = (BS18 + BS19 + BS20) / (BS11 + BS12 + BS10)
                                     (inv + debtors + cash) / (creditors + other CL + WC borrowing)
    Ratios r7  Debt-Equity        = (BS9 + BS10) / BS8
                                     (term loan closing + WC borrowing) / net worth
    Ratios r8  TOL / TNW          = (BS9 + BS10 + BS11 + BS12) / BS8
                                     (term loan + WC borrowing + creditors + other CL) / net worth
    Ratios r10 EBITDA Margin      = AnnualSummary22 / AnnualSummary8   (EBITDA / net sales)
    Ratios r11 Net Profit Margin  = AnnualSummary26 / AnnualSummary8   (PAT / net sales)
    Ratios r12 ROCE               = AnnualSummary23 / (BS8 + BS9)      (EBIT / (net worth + term loan))
    Ratios r14 Interest Coverage  = AnnualSummary23 / (AS19 + AS20)    (EBIT / (TL int + WC int))
    Ratios r15 DSCR               = DSCR!<y>14
    Ratios r16 Break-even (% sales)= FixedCosts / Contribution         (see classification below)

    DSCR   r9  Cash Available (A) = PAT + Depreciation + TL interest
    DSCR   r13 Debt Obligation (B)= Principal + TL interest
    DSCR   r14 DSCR               = IFERROR(A / B, 0)
    DSCR   H14 Average DSCR       = AVERAGE(<y>14 across the 5 years)

BREAK-EVEN COST CLASSIFICATION (straight from the Excel, not a guess):
    Fixed (numerator):      wages, factory overheads, repairs, admin, depreciation,
                            TL interest, WC interest
    Variable (contribution): net sales - (cost1 + cost2 + other_variable + selling&distribution)
    So selling & distribution is treated as VARIABLE (it is a % of revenue), while
    admin, depreciation and both interest lines are FIXED.

DEPENDENCIES / WHY SOME THINGS ARE RECOMPUTED HERE
--------------------------------------------------
This module is a CONSUMER of the other calculators. Two values it needs are not
present in the five parameters, so — exactly as balance_sheet_calc recomputes the
loan schedule from `assumptions` — they are derived here from `assumptions`:

  * The per-line ANNUAL OPERATING EXPENSES (wages, factory_oh, repairs, admin, cost1,
    cost2, other_variable, selling&distribution) that break-even needs. `pl` returns
    only aggregates and `wc_data` only net_sales/purchases/cost_of_production, so the
    breakdown is recomputed from revenue_calc + expense_calc (pure, deterministic).
  * ANNUAL DEPRECIATION for the DSCR add-back and the break-even fixed block, from
    depreciation_calc.

Everything else comes from the passed dicts: net sales from wc_data['net_sales'];
EBITDA/EBIT/PAT from pl; the balance-sheet lines from balance_sheet; TL interest and
principal from loan_schedule; WC interest from wc_data['wc_interest_annual'].

DSCR is intentionally folded in rather than living in a separate dscr_calc.py: every
input (PAT, depreciation, TL interest, principal) is already available here, so a
separate module would add a file without adding capability.

Pure functions: no I/O, no AI, no Excel, no file access.
"""

from .revenue_calc import calculate_monthly_production, calculate_monthly_revenue, yearly_totals
from .expense_calc import calculate_monthly_variable_costs, calculate_monthly_fixed_costs
from .depreciation_calc import calculate_annual_depreciation

YEARS = 5


def _require_dict(d, name: str, keys, fn: str) -> None:
    if not isinstance(d, dict):
        raise ValueError(f"{fn}: {name} must be a dict, got {type(d).__name__}")
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"{fn}: {name} is missing required key(s): {', '.join(missing)}")


def _annual(series, name: str, fn: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != YEARS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn}: {name} must be a list of {YEARS} annual values, got {got}")
    out = []
    for i, v in enumerate(series):
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            raise ValueError(f"{fn}: {name}[{i}] must be numeric, got {v!r}")
    return out


def _div(num: float, den: float) -> float:
    """Mirror Excel IFERROR(num/den, 0): a zero (or non-finite) denominator -> 0."""
    if den == 0:
        return 0.0
    return num / den


def calculate_ratios(
    assumptions: dict,
    pl: dict,
    balance_sheet: dict,
    loan_schedule: dict,
    wc_data: dict,
    cost_lines: dict = None,
) -> dict:
    """Mirrors the Ratios sheet exactly, plus DSCR (per-year + average). Returns each
    ratio as a 5-year list, and average_dscr as a single value.

    `cost_lines` (optional): the monthly cost breakdown already built upstream,
    {"var": {...}, "fix": {...}}. When given it is used as-is instead of recomputing
    the breakdown from `assumptions`. For manufacturing the two are identical (same
    functions, same inputs), so this changes no manufacturing number; for industries
    whose costs are not built by the manufacturing formulas (retail's COGS via gross
    margin), it is what makes the break-even ratio correct rather than recomputing a
    factory breakdown the industry never had."""
    fn = "calculate_ratios"
    _require_dict(pl, "pl", ("ebitda", "ebit", "pat"), fn)
    _require_dict(balance_sheet, "balance_sheet",
                  ("net_worth", "term_loan_closing", "wc_borrowing", "sundry_creditors",
                   "other_current_liabilities", "inventory", "debtors",
                   "cash_balancing_figure"), fn)
    _require_dict(loan_schedule, "loan_schedule", ("interest", "principal"), fn)
    _require_dict(wc_data, "wc_data", ("net_sales", "wc_interest_annual"), fn)

    # ── from the passed dicts ───────────────────────────────────────────────────
    ebitda = _annual(pl["ebitda"], "pl['ebitda']", fn)
    ebit = _annual(pl["ebit"], "pl['ebit']", fn)
    pat = _annual(pl["pat"], "pl['pat']", fn)

    net_worth = _annual(balance_sheet["net_worth"], "balance_sheet['net_worth']", fn)
    term_loan = _annual(balance_sheet["term_loan_closing"], "balance_sheet['term_loan_closing']", fn)
    wc_borrow = _annual(balance_sheet["wc_borrowing"], "balance_sheet['wc_borrowing']", fn)
    creditors = _annual(balance_sheet["sundry_creditors"], "balance_sheet['sundry_creditors']", fn)
    other_cl = _annual(balance_sheet["other_current_liabilities"],
                       "balance_sheet['other_current_liabilities']", fn)
    inventory = _annual(balance_sheet["inventory"], "balance_sheet['inventory']", fn)
    debtors = _annual(balance_sheet["debtors"], "balance_sheet['debtors']", fn)
    cash = _annual(balance_sheet["cash_balancing_figure"],
                   "balance_sheet['cash_balancing_figure']", fn)

    tl_interest = _annual(loan_schedule["interest"], "loan_schedule['interest']", fn)
    principal = _annual(loan_schedule["principal"], "loan_schedule['principal']", fn)

    net_sales = _annual(wc_data["net_sales"], "wc_data['net_sales']", fn)
    wc_interest = _annual(wc_data["wc_interest_annual"], "wc_data['wc_interest_annual']", fn)

    # ── cost breakdown: use the one built upstream, or recompute from assumptions ──
    if cost_lines and cost_lines.get("var") and cost_lines.get("fix"):
        var = cost_lines["var"]
        fix = cost_lines["fix"]
    else:
        production = calculate_monthly_production(assumptions)
        revenue_m = calculate_monthly_revenue(assumptions, production)
        var = calculate_monthly_variable_costs(assumptions, production)
        fix = calculate_monthly_fixed_costs(assumptions, revenue_m)
    dep_annual = calculate_annual_depreciation(assumptions)          # flat, one value

    cost1 = yearly_totals(var["cost1"])
    cost2 = yearly_totals(var["cost2"])
    other_variable = yearly_totals(var["other_variable"])
    wages = yearly_totals(fix["wages"])
    factory_oh = yearly_totals(fix["factory_overheads"])
    repairs = yearly_totals(fix["repairs_maintenance"])
    admin = yearly_totals(fix["admin_expenses"])
    selling_dist = yearly_totals(fix["selling_distribution"])

    # ── ratios ──────────────────────────────────────────────────────────────────
    current_ratio, debt_equity, tol_tnw = [], [], []
    ebitda_margin, net_profit_margin, roce, interest_coverage, break_even = [], [], [], [], []
    cash_available, debt_obligation, dscr = [], [], []

    for y in range(YEARS):
        # r6: current assets / current liabilities (WC borrowing is a current liability)
        current_ratio.append(_div(inventory[y] + debtors[y] + cash[y],
                                  creditors[y] + other_cl[y] + wc_borrow[y]))
        # r7: (term loan + WC borrowing) / net worth
        debt_equity.append(_div(term_loan[y] + wc_borrow[y], net_worth[y]))
        # r8: total outside liabilities / tangible net worth
        tol_tnw.append(_div(term_loan[y] + wc_borrow[y] + creditors[y] + other_cl[y], net_worth[y]))
        # r10 / r11: margins on net sales
        ebitda_margin.append(_div(ebitda[y], net_sales[y]))
        net_profit_margin.append(_div(pat[y], net_sales[y]))
        # r12: EBIT / (net worth + term loan closing)
        roce.append(_div(ebit[y], net_worth[y] + term_loan[y]))
        # r14: EBIT / total interest
        interest_coverage.append(_div(ebit[y], tl_interest[y] + wc_interest[y]))

        # r16: fixed costs / contribution
        fixed_costs = (wages[y] + factory_oh[y] + repairs[y] + admin[y]
                       + dep_annual + tl_interest[y] + wc_interest[y])
        contribution = net_sales[y] - (cost1[y] + cost2[y] + other_variable[y] + selling_dist[y])
        break_even.append(_div(fixed_costs, contribution))

        # DSCR sheet: (PAT + depreciation + TL interest) / (principal + TL interest)
        a = pat[y] + dep_annual + tl_interest[y]
        b = principal[y] + tl_interest[y]
        cash_available.append(a)
        debt_obligation.append(b)
        dscr.append(_div(a, b))

    average_dscr = sum(dscr) / len(dscr) if dscr else 0.0   # DSCR!H14 = AVERAGE(C14:G14)

    return {
        "current_ratio": current_ratio,
        "debt_equity": debt_equity,
        "tol_tnw": tol_tnw,
        "ebitda_margin": ebitda_margin,
        "net_profit_margin": net_profit_margin,
        "return_on_capital_employed": roce,
        "interest_coverage": interest_coverage,
        "break_even_pct": break_even,
        "dscr": dscr,
        "average_dscr": average_dscr,
        "cash_available_for_debt_service": cash_available,
        "total_debt_obligation": debt_obligation,
    }
