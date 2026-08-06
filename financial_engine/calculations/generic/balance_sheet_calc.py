"""
balance_sheet_calc.py

Industry-agnostic projected balance sheet. A line-for-line mirror of the Bank Loan
CMA workbook's **Form_III_BalanceSheet**.

The Excel formulas being reproduced (<y> = this year's column, <y-1> = prior year):

    LIABILITIES
    r6   Capital / Promoters' equity   = Assumptions!$C$9                (flat)
    r7   Reserves & surplus            = Y1: Annual_Summary!C26
                                         Y2+: <y-1>7 + Annual_Summary!<y>26   (cumulative PAT)
    r8   Net Worth                     = <y>6 + <y>7
    r9   Term loan (closing balance)   = Repayment!<y>8
    r10  Bank borrowing - working cap. = Form_V_MPBF!<y>11               (recommended MPBF)
    r11  Sundry creditors              = Form_IV_CA_CL!<y>16
    r12  Other current liabilities     = Form_IV_CA_CL!<y>17             (= 0)
    r13  TOTAL LIABILITIES             = SUM(<y>8:<y>12)

    ASSETS
    r15  Gross fixed assets            = C42 + C43 + C45 + C47           (flat, INCLUDES land)
    r16  (-) Accumulated depreciation  = Y1: Annual_Summary!C18
                                         Y2+: <y-1>16 + Annual_Summary!<y>18  (cumulative)
    r17  Net fixed assets              = <y>15 - <y>16
    r18  Inventory                     = Form_IV_CA_CL!<y>10 + <y>11     (RM + FG)
    r19  Sundry debtors                = Form_IV_CA_CL!<y>12
    r20  Cash & bank (balancing figure)= <y>13 - (<y>17 + <y>18 + <y>19)
    r21  TOTAL ASSETS                  = <y>17 + <y>18 + <y>19 + <y>20
    r22  Check (Liab - Assets)         = <y>13 - <y>21

Mapped to schema field names (assumption_schema.json):

    C9  promoters_capital
    C42 land_cost   C43 building_cost   C45 plant_machinery_cost   C47 furniture_other_cost

THREE FACTS REPRODUCED DELIBERATELY, each with a consequence worth stating:

  1. CUMULATIVE (LEFT-FOLD) STATE. Reserves (r7) and accumulated depreciation (r16)
     each reference the PRIOR YEAR's own cell and add this year's value — so they are
     running sums, not per-year figures. This is the first calculator where a year
     genuinely depends on prior-year state; it MUST fold left, not map independently.
     Reserves = 100% of PAT retained (no dividends, no drawings). Promoters' equity
     (r6) is flat — no equity infusion after Year 1.

  2. GROSS FIXED ASSETS INCLUDE LAND. r15 sums land + building + plant&machinery +
     furniture. Land is (correctly) NOT in the depreciation base, so net fixed assets
     never fall below the land value — land is carried at cost forever.

  3. THE BALANCE CHECK IS A TAUTOLOGY, NOT A VALIDATION. Cash (r20) is the balancing
     plug: r20 = TotalLiab - (NetFA + Inventory + Debtors). Substituting into r21
     gives TotalAssets == TotalLiabilities identically, so r22 is ALWAYS ~0 by
     construction — it can never detect an unbalanced or unsound model. The real
     failure mode it hides is NEGATIVE CASH: when liabilities are too small to fund
     the assets, the plug goes negative (a genuine funding shortfall) while r22 still
     reads 0. We reproduce r22 == 0 for parity AND expose negative_cash_flag, which is
     the actual solvency signal.

This module is a CONSUMER of the other calculators: annual PAT (from profit_calc),
annual depreciation (from depreciation_calc), the loan schedule (computed here from
assumptions), and working capital (from working_capital_calc).

Pure functions: no I/O, no AI, no Excel, no file access.
"""

from .loan_schedule_calc import calculate_loan_schedule

YEARS = 5

# Balance-sheet-specific inputs (loan + WC fields are validated by their own modules).
_REQUIRED_KEYS = (
    "promoters_capital",
    "land_cost",
    "building_cost",
    "plant_machinery_cost",
    "furniture_other_cost",
)

# wc_data keys this module reads (produced by working_capital_calc).
_REQUIRED_WC_KEYS = ("mpbf", "creditors", "rm_inventory", "fg_inventory", "receivables")


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


def _annual(series, name: str, fn: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != YEARS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn}: {name} must be a list of {YEARS} annual values, got {got}")
    return [_num(v, f"{name}[{i}]") for i, v in enumerate(series)]


def _wc_series(wc_data: dict, key: str, fn: str) -> list:
    if not isinstance(wc_data, dict):
        raise ValueError(f"{fn}: wc_data must be a dict, got {type(wc_data).__name__}")
    if key not in wc_data:
        raise ValueError(f"{fn}: wc_data is missing required key {key!r} "
                         f"(expected from working_capital_calc)")
    return _annual(wc_data[key], f"wc_data['{key}']", fn)


def _cumulative(annual: list) -> list:
    """Left-fold running sum: out[i] = out[i-1] + annual[i]. This is the r7 / r16
    carry-forward — each year builds on the prior year's balance."""
    out, running = [], 0.0
    for v in annual:
        running += v
        out.append(running)
    return out


def calculate_balance_sheet(
    assumptions: dict,
    annual_pat: list,
    annual_depreciation_total: list,
    wc_data: dict,
) -> dict:
    """Mirrors Form_III_BalanceSheet exactly, including its cumulative (left-fold)
    reserves and accumulated-depreciation logic. Returns 5-year lists per line, the
    tautological balance_check, and negative_cash_flag (the real solvency signal)."""
    fn = "calculate_balance_sheet"
    _require(assumptions, _REQUIRED_KEYS, fn)
    for k in _REQUIRED_WC_KEYS:
        _wc_series(wc_data, k, fn)  # validate presence/shape up front

    pat = _annual(annual_pat, "annual_pat", fn)
    dep = _annual(annual_depreciation_total, "annual_depreciation_total", fn)

    # ── Liabilities ────────────────────────────────────────────────────────────
    promoters = _num(assumptions["promoters_capital"], "promoters_capital")
    promoters_equity = [promoters] * YEARS                          # r6 (flat)
    reserves_surplus = _cumulative(pat)                             # r7 (cumulative PAT)
    net_worth = [e + r for e, r in zip(promoters_equity, reserves_surplus)]  # r8

    term_loan_closing = calculate_loan_schedule(assumptions)["closing_balance"]  # r9
    wc_borrowing = _wc_series(wc_data, "mpbf", fn)                  # r10
    sundry_creditors = _wc_series(wc_data, "creditors", fn)         # r11
    other_current_liabilities = [0.0] * YEARS                      # r12 (= 0)

    total_liabilities = [                                           # r13 = SUM(r8:r12)
        nw + tl + wcb + sc + ocl
        for nw, tl, wcb, sc, ocl in zip(
            net_worth, term_loan_closing, wc_borrowing,
            sundry_creditors, other_current_liabilities)
    ]

    # ── Assets ─────────────────────────────────────────────────────────────────
    gross = (_num(assumptions["land_cost"], "land_cost")
             + _num(assumptions["building_cost"], "building_cost")
             + _num(assumptions["plant_machinery_cost"], "plant_machinery_cost")
             + _num(assumptions["furniture_other_cost"], "furniture_other_cost"))
    gross_fixed_assets = [gross] * YEARS                           # r15 (flat, incl. land)
    accumulated_depreciation = _cumulative(dep)                    # r16 (cumulative)
    net_fixed_assets = [g - a for g, a in zip(gross_fixed_assets, accumulated_depreciation)]  # r17

    rm = _wc_series(wc_data, "rm_inventory", fn)
    fg = _wc_series(wc_data, "fg_inventory", fn)
    inventory = [r + f for r, f in zip(rm, fg)]                     # r18 (RM + FG)
    debtors = _wc_series(wc_data, "receivables", fn)               # r19

    # r20: cash is the BALANCING PLUG, not an independently-computed figure.
    cash_balancing_figure = [
        tl - (nfa + inv + deb)
        for tl, nfa, inv, deb in zip(total_liabilities, net_fixed_assets, inventory, debtors)
    ]
    total_assets = [                                               # r21
        nfa + inv + deb + cash
        for nfa, inv, deb, cash in zip(net_fixed_assets, inventory, debtors, cash_balancing_figure)
    ]

    # r22: Liab - Assets. Zero BY CONSTRUCTION (cash is the plug) — a tautology, not a
    # validation. Reproduced for parity; real solvency lives in negative_cash_flag.
    balance_check = [tl - ta for tl, ta in zip(total_liabilities, total_assets)]
    negative_cash_flag = [c < 0 for c in cash_balancing_figure]

    return {
        "promoters_equity": promoters_equity,
        "reserves_surplus": reserves_surplus,
        "net_worth": net_worth,
        "term_loan_closing": term_loan_closing,
        "wc_borrowing": wc_borrowing,
        "sundry_creditors": sundry_creditors,
        "other_current_liabilities": other_current_liabilities,
        "total_liabilities": total_liabilities,
        "gross_fixed_assets": gross_fixed_assets,
        "accumulated_depreciation": accumulated_depreciation,
        "net_fixed_assets": net_fixed_assets,
        "inventory": inventory,
        "debtors": debtors,
        "cash_balancing_figure": cash_balancing_figure,
        "total_assets": total_assets,
        "balance_check": balance_check,
        "negative_cash_flag": negative_cash_flag,
    }
