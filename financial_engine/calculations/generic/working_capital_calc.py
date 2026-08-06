"""
working_capital_calc.py

Industry-agnostic working-capital build-up and the bank finance limit derived from
it. Mirrors three parts of the Bank Loan CMA workbook:

  Form_IV_CA_CL  — current assets / current liabilities build-up
  Form_V_MPBF    — Maximum Permissible Bank Finance, Tandon Method II
  Expenses!r15   — the working-capital interest line

The Excel formulas being reproduced (column C = Year 1):

    Form_IV r7   Purchases (raw material) = Annual_Summary!C10   (= annual cost1)
    Form_IV r8   Net Sales                = Annual_Summary!C8    (= annual revenue)
    Form_IV r6   Cost of Production       = Annual_Summary C10+C11+C12+C13+C14+C15+C18

    Form_IV r10  Inventory - raw material = Purchases        * C50/365
    Form_IV r11  Inventory - finished gds = CostOfProduction * C51/365
    Form_IV r12  Sundry debtors           = NetSales         * C52/365
    Form_IV r13  Cash & bank (minimum)    = C54                        (flat)
    Form_IV r14  Total Current Assets     = SUM(r10:r13)

    Form_IV r16  Sundry creditors         = Purchases        * C53/365
    Form_IV r17  Other current liabilities= 0
    Form_IV r18  Total Current Liabilities= r16 + r17
    Form_IV r19  Working Capital Gap      = r14 - r18

    Form_V  r10  MPBF Method II  = MAX(0, TCA * (1 - C55) - TCL)
    Form_V  r11  Recommended MPBF = r10                       (Method II is the one used)

    Expenses r15 WC interest (monthly) = Form_V!<year>11 * C13 / 12
                 -> annual WC interest = MPBF(year) * interest_rate_wc

Mapped to schema field names (assumption_schema.json):

    C50 raw_material_holding_days     C51 finished_goods_holding_days
    C52 receivables_days              C53 payables_days
    C54 min_cash_balance              C55 wc_margin_pct
    C13 interest_rate_wc

ON THE "CIRCULAR DEPENDENCY"
---------------------------
It is natural to assume WC interest is circular: WC interest depends on MPBF, which
depends on Cost of Production, which is an operating cost — so surely Cost of
Production includes WC interest?

It does NOT, in this workbook. Form_IV's Cost of Production is
Annual_Summary C10+C11+C12+C13+C14+C15+C18 = cost1 + cost2 + wages + other_variable
+ factory_overheads + repairs + depreciation. Interest on the term loan (C19) and
interest on working capital (C20) are BOTH excluded, as are admin (C16) and selling
& distribution (C17). So the dependency runs one way only and the Excel resolves it
in a single pass — there is no feedback loop to converge.

The iterate-to-convergence machinery below is retained anyway, because it is the
correct shape for this calculation and would be required if Cost of Production were
ever redefined to include interest. Against the current workbook it converges on the
FIRST iteration, and `iterations_used` in the return value proves that rather than
leaving it as an assertion. Pass `cost_of_production_includes_wc_interest=True` to
model the genuinely circular variant.

Pure functions: no I/O, no AI, no Excel, no file access.
"""

DAYS_PER_YEAR = 365
YEARS = 5

_REQUIRED_KEYS = (
    "raw_material_holding_days",
    "finished_goods_holding_days",
    "receivables_days",
    "payables_days",
    "min_cash_balance",
    "wc_margin_pct",
)


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


def _check_annual(series, name: str, fn_name: str) -> list:
    if not isinstance(series, (list, tuple)) or len(series) != YEARS:
        got = len(series) if isinstance(series, (list, tuple)) else type(series).__name__
        raise ValueError(f"{fn_name}: {name} must be a list of {YEARS} annual values, got {got}")
    return [_num(v, f"{name}[{i}]") for i, v in enumerate(series)]


def calculate_working_capital(
    assumptions: dict,
    annual_revenue: list,
    annual_cost_of_production_ex_wc_interest: list,
    wc_interest_rate: float = None,
    annual_purchases: list = None,
    max_iterations: int = 10,
    tolerance: float = 0.01,
    cost_of_production_includes_wc_interest: bool = False,
) -> dict:
    """Working-capital build-up, MPBF (Tandon Method II) and WC interest, per year.

    Args:
        annual_revenue: 5 annual net-sales figures (Form_IV r8).
        annual_cost_of_production_ex_wc_interest: 5 annual cost-of-production
            figures EXCLUDING working-capital interest (Form_IV r6).
        wc_interest_rate: interest_rate_wc. Falls back to assumptions["interest_rate_wc"].
        annual_purchases: 5 annual raw-material purchase figures (Form_IV r7 =
            annual cost1). Defaults to cost-of-production if not supplied, but the
            Excel uses cost1 specifically, so pass it.
        cost_of_production_includes_wc_interest: False mirrors the workbook (no
            circularity). True models the circular variant, in which case the loop
            genuinely iterates.

    Returns a dict of 5-element lists plus `iterations_used` and `converged`.
    """
    fn = "calculate_working_capital"
    _require(assumptions, _REQUIRED_KEYS, fn)

    rate = wc_interest_rate if wc_interest_rate is not None else assumptions.get("interest_rate_wc")
    if rate is None:
        raise ValueError(f"{fn}: wc_interest_rate not given and 'interest_rate_wc' "
                         f"is absent from assumptions.")
    rate = _num(rate, "interest_rate_wc")

    revenue = _check_annual(annual_revenue, "annual_revenue", fn)
    cop_base = _check_annual(annual_cost_of_production_ex_wc_interest,
                             "annual_cost_of_production_ex_wc_interest", fn)
    purchases = (_check_annual(annual_purchases, "annual_purchases", fn)
                 if annual_purchases is not None else list(cop_base))

    rm_days = _num(assumptions["raw_material_holding_days"], "raw_material_holding_days")
    fg_days = _num(assumptions["finished_goods_holding_days"], "finished_goods_holding_days")
    rec_days = _num(assumptions["receivables_days"], "receivables_days")
    pay_days = _num(assumptions["payables_days"], "payables_days")
    min_cash = _num(assumptions["min_cash_balance"], "min_cash_balance")
    margin = _num(assumptions["wc_margin_pct"], "wc_margin_pct")

    if max_iterations < 1:
        raise ValueError(f"{fn}: max_iterations must be >= 1, got {max_iterations}")

    wc_interest = [0.0] * YEARS          # seed the loop with zero WC interest
    iterations_used = 0
    converged = False
    result = {}

    for _ in range(max_iterations):
        iterations_used += 1

        # Cost of Production for this pass. Mirroring the workbook, WC interest is
        # NOT part of it — so this is a no-op and the loop settles immediately.
        cop = ([c + w for c, w in zip(cop_base, wc_interest)]
               if cost_of_production_includes_wc_interest else list(cop_base))

        rm_inv = [p * rm_days / DAYS_PER_YEAR for p in purchases]          # Form_IV r10
        fg_inv = [c * fg_days / DAYS_PER_YEAR for c in cop]                # Form_IV r11
        debtors = [r * rec_days / DAYS_PER_YEAR for r in revenue]          # Form_IV r12
        cash = [min_cash] * YEARS                                          # Form_IV r13
        tca = [a + b + c + d for a, b, c, d in zip(rm_inv, fg_inv, debtors, cash)]

        creditors = [p * pay_days / DAYS_PER_YEAR for p in purchases]      # Form_IV r16
        other_cl = [0.0] * YEARS                                           # Form_IV r17
        tcl = [a + b for a, b in zip(creditors, other_cl)]                 # Form_IV r18
        wc_gap = [a - b for a, b in zip(tca, tcl)]                         # Form_IV r19

        min_nwc = [margin * a for a in tca]                                # Form_V  r8
        mpbf_i = [max(0.0, g * (1.0 - margin)) for g in wc_gap]            # Form_V  r9
        mpbf_ii = [max(0.0, a * (1.0 - margin) - l) for a, l in zip(tca, tcl)]  # Form_V r10
        mpbf = list(mpbf_ii)                                               # Form_V  r11

        new_wc_interest = [m * rate for m in mpbf]                         # Expenses r15 (annual)

        # convergence: largest relative move in WC interest between passes
        deltas = []
        for new, old in zip(new_wc_interest, wc_interest):
            denom = abs(old) if abs(old) > 1e-9 else (abs(new) if abs(new) > 1e-9 else 1.0)
            deltas.append(abs(new - old) / denom)
        moved = max(deltas) if deltas else 0.0
        wc_interest = new_wc_interest

        result = {
            "purchases": purchases,
            "cost_of_production": cop,
            "net_sales": revenue,
            "rm_inventory": rm_inv,
            "fg_inventory": fg_inv,
            "receivables": debtors,
            "cash": cash,
            "total_current_assets": tca,
            "creditors": creditors,
            "other_current_liabilities": other_cl,
            "total_current_liabilities": tcl,
            "working_capital_gap": wc_gap,
            "min_stipulated_nwc": min_nwc,
            "mpbf_method_i": mpbf_i,
            "mpbf_method_ii": mpbf_ii,
            "mpbf": mpbf,
            "wc_interest_annual": list(wc_interest),
            "wc_interest_monthly": [w / 12.0 for w in wc_interest],
        }

        if not cost_of_production_includes_wc_interest or moved <= tolerance:
            converged = True
            break

    result["iterations_used"] = iterations_used
    result["converged"] = converged
    if not converged:
        # Never silently return a half-converged answer as if it were exact.
        result["warning"] = (
            f"WC interest did not converge within {max_iterations} iterations "
            f"(tolerance {tolerance}). Values are approximate."
        )
    return result
