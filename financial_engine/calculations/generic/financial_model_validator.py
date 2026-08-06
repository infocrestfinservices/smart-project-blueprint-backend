"""
financial_model_validator.py

A standalone quality-assurance layer for the generic financial engine. It VERIFIES
CONSISTENCY between outputs already produced by the other modules — it performs NO
business calculations of its own and never re-derives a business value. Its only
arithmetic is the minimum needed to check a relationship (a subtraction, a division,
or NPV-at-a-given-rate) between numbers it is handed.

It knows nothing about Bank Loan, Feasibility, or any report purpose, and touches no
Excel/template/LibreOffice.

CONTRACT (with aliases so the real modules plug in). All yearly lists are length N,
EXCEPT the cash-flow lists which are length N+1 (Year 0..Year N):

  assumptions              : loan_amount | term_loan_amount
  profit_output            : revenue, expenses, ebitda, ebit, pbt, tax|income_tax, pat
  depreciation_output      : dict{annual_depreciation|depreciation} OR a bare list
  working_capital_output   : current_assets|total_current_assets,
                             current_liabilities|total_current_liabilities,
                             working_capital|working_capital_gap,
                             (optional) wc_interest_annual
  loan_schedule_output     : opening_balance, interest, principal, closing_balance
  cash_flow_output         : operating_cash_flow, investing_cash_flow,
                             financing_cash_flow, net_cash_flow, cash_flow_series
  balance_sheet_output     : total_assets, total_liabilities, total_equity
  ratio_output             : dscr, interest_coverage, current_ratio,
                             cash_available_for_debt_service, total_debt_obligation
  irr_npv_output           : irr (float|None), npv (float)

RESULT: {"passed": bool, "warnings": [str], "errors": [str]}. `passed` is
True iff `errors` is empty. Every consistency failure is collected (the function does
NOT stop at the first). ValueError is raised ONLY for MALFORMED INPUTS — missing
required keys, wrong types, or inconsistent series lengths — never for a mere
reconciliation failure.

Pure function. No I/O, no dependency on the other modules.
"""

from __future__ import annotations

import math
from typing import List, Optional


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _require_dict(d, name: str, fn: str) -> None:
    if not isinstance(d, dict):
        raise ValueError(f"{fn}: {name} must be a dict, got {type(d).__name__}")


def _series(d: dict, name: str, aliases, fn: str, expected_len: Optional[int]) -> List[float]:
    """Fetch a numeric yearly list under the first present alias. Raises ValueError on
    a missing key, non-list value, non-numeric element, or wrong length."""
    chosen = None
    for key in aliases:
        if key in d:
            chosen = key
            break
    if chosen is None:
        raise ValueError(f"{fn}: {name} is missing a required key "
                         f"(expected one of: {', '.join(aliases)})")
    val = d[chosen]
    if not isinstance(val, (list, tuple)):
        raise ValueError(f"{fn}: {name}[{chosen!r}] must be a list, got {type(val).__name__}")
    for i, v in enumerate(val):
        if not _is_num(v):
            raise ValueError(f"{fn}: {name}[{chosen!r}][{i}] must be numeric, got {v!r}")
    out = [float(v) for v in val]
    if expected_len is not None and len(out) != expected_len:
        raise ValueError(f"{fn}: {name}[{chosen!r}] has length {len(out)}, expected {expected_len}")
    return out


def _dep_series(dep, n: int, fn: str) -> List[float]:
    """depreciation_output is intentionally untyped: accept a dict (annual_depreciation
    / depreciation) or a bare list, since depreciation_calc returns a list/scalar."""
    if isinstance(dep, dict):
        return _series(dep, "depreciation_output", ("annual_depreciation", "depreciation"), fn, n)
    if isinstance(dep, (list, tuple)):
        for i, v in enumerate(dep):
            if not _is_num(v):
                raise ValueError(f"{fn}: depreciation_output[{i}] must be numeric, got {v!r}")
        out = [float(v) for v in dep]
        if len(out) != n:
            raise ValueError(f"{fn}: depreciation_output has length {len(out)}, expected {n}")
        return out
    raise ValueError(f"{fn}: depreciation_output must be a dict or list, got {type(dep).__name__}")


def _assumption_num(assumptions: dict, aliases, label: str, fn: str) -> float:
    for key in aliases:
        if assumptions.get(key) is not None:
            v = assumptions[key]
            if not _is_num(v):
                raise ValueError(f"{fn}: assumptions[{key!r}] must be numeric, got {v!r}")
            return float(v)
    raise ValueError(f"{fn}: assumptions must provide {label} (one of: {', '.join(aliases)}).")


def validate_financial_model(
    assumptions: dict,
    profit_output: dict,
    depreciation_output,
    working_capital_output: dict,
    loan_schedule_output: dict,
    cash_flow_output: dict,
    balance_sheet_output: dict,
    ratio_output: dict,
    irr_npv_output: dict,
    *,
    tolerance: float = 1e-2,
) -> dict:
    """Verify consistency across the engine's outputs. Returns
    {passed, warnings, errors}. Raises ValueError only for malformed inputs."""
    fn = "validate_financial_model"
    errors: List[str] = []
    warnings: List[str] = []

    def close(a: float, b: float) -> bool:
        return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)

    # ── structural validation (raise on malformed input) ────────────────────────
    for name, d in (("assumptions", assumptions), ("profit_output", profit_output),
                    ("working_capital_output", working_capital_output),
                    ("loan_schedule_output", loan_schedule_output),
                    ("cash_flow_output", cash_flow_output),
                    ("balance_sheet_output", balance_sheet_output),
                    ("ratio_output", ratio_output), ("irr_npv_output", irr_npv_output)):
        _require_dict(d, name, fn)

    pat = _series(profit_output, "profit_output", ("pat",), fn, None)
    n = len(pat)
    if n < 1:
        raise ValueError(f"{fn}: profit_output['pat'] must have at least 1 year")

    revenue = _series(profit_output, "profit_output", ("revenue",), fn, n)
    expenses = _series(profit_output, "profit_output", ("expenses",), fn, n)
    ebitda = _series(profit_output, "profit_output", ("ebitda",), fn, n)
    ebit = _series(profit_output, "profit_output", ("ebit",), fn, n)
    pbt = _series(profit_output, "profit_output", ("pbt",), fn, n)
    tax = _series(profit_output, "profit_output", ("tax", "income_tax"), fn, n)

    dep = _dep_series(depreciation_output, n, fn)

    ca = _series(working_capital_output, "working_capital_output",
                 ("current_assets", "total_current_assets"), fn, n)
    cl = _series(working_capital_output, "working_capital_output",
                 ("current_liabilities", "total_current_liabilities"), fn, n)
    wc = _series(working_capital_output, "working_capital_output",
                 ("working_capital", "working_capital_gap"), fn, n)
    wc_interest = ([0.0] * n)
    if any(k in working_capital_output for k in ("wc_interest_annual", "wc_interest")):
        wc_interest = _series(working_capital_output, "working_capital_output",
                              ("wc_interest_annual", "wc_interest"), fn, n)
    else:
        warnings.append("W: working_capital_output has no 'wc_interest_annual'; "
                        "assuming 0 WC interest for the interest reconciliation.")

    opening = _series(loan_schedule_output, "loan_schedule_output", ("opening_balance",), fn, n)
    interest = _series(loan_schedule_output, "loan_schedule_output", ("interest",), fn, n)
    principal = _series(loan_schedule_output, "loan_schedule_output", ("principal",), fn, n)
    closing = _series(loan_schedule_output, "loan_schedule_output", ("closing_balance",), fn, n)

    # cash-flow lists are length N+1 (Year 0..Year N)
    op_cf = _series(cash_flow_output, "cash_flow_output", ("operating_cash_flow",), fn, n + 1)
    inv_cf = _series(cash_flow_output, "cash_flow_output", ("investing_cash_flow",), fn, n + 1)
    fin_cf = _series(cash_flow_output, "cash_flow_output", ("financing_cash_flow",), fn, n + 1)
    net_cf = _series(cash_flow_output, "cash_flow_output", ("net_cash_flow",), fn, n + 1)
    cf_series = _series(cash_flow_output, "cash_flow_output", ("cash_flow_series",), fn, n + 1)

    total_assets = _series(balance_sheet_output, "balance_sheet_output", ("total_assets",), fn, n)
    total_liab = _series(balance_sheet_output, "balance_sheet_output", ("total_liabilities",), fn, n)
    total_equity = _series(balance_sheet_output, "balance_sheet_output", ("total_equity",), fn, n)

    dscr = _series(ratio_output, "ratio_output", ("dscr",), fn, n)
    icr = _series(ratio_output, "ratio_output", ("interest_coverage",), fn, n)
    curr_ratio = _series(ratio_output, "ratio_output", ("current_ratio",), fn, n)
    cash_avail = _series(ratio_output, "ratio_output",
                         ("cash_available_for_debt_service", "cash_available"), fn, n)
    debt_service = _series(ratio_output, "ratio_output",
                           ("total_debt_obligation", "debt_service"), fn, n)

    if "irr" not in irr_npv_output:
        raise ValueError(f"{fn}: irr_npv_output is missing required key 'irr'")
    irr = irr_npv_output["irr"]
    if irr is not None and not _is_num(irr):
        raise ValueError(f"{fn}: irr_npv_output['irr'] must be a number or None, got {irr!r}")

    loan_amount = _assumption_num(assumptions, ("loan_amount", "term_loan_amount"),
                                  "the loan amount", fn)

    interest_total = [interest[t] + wc_interest[t] for t in range(n)]

    # ── consistency checks (collect all; never raise) ───────────────────────────
    # R1: Revenue - Expenses = EBITDA
    for t in range(n):
        if not close(revenue[t] - expenses[t], ebitda[t]):
            errors.append(f"R1 (Revenue-Expenses=EBITDA) yr{t+1}: "
                          f"{revenue[t]:.2f}-{expenses[t]:.2f}={revenue[t]-expenses[t]:.2f} != EBITDA {ebitda[t]:.2f}")
    # R2: EBITDA - Depreciation = EBIT
    for t in range(n):
        if not close(ebitda[t] - dep[t], ebit[t]):
            errors.append(f"R2 (EBITDA-Deprec=EBIT) yr{t+1}: "
                          f"{ebitda[t]:.2f}-{dep[t]:.2f}={ebitda[t]-dep[t]:.2f} != EBIT {ebit[t]:.2f}")
    # R3: EBIT - Interest = PBT
    for t in range(n):
        if not close(ebit[t] - interest_total[t], pbt[t]):
            errors.append(f"R3 (EBIT-Interest=PBT) yr{t+1}: "
                          f"{ebit[t]:.2f}-{interest_total[t]:.2f}={ebit[t]-interest_total[t]:.2f} != PBT {pbt[t]:.2f}")
    # R4: PBT - Tax = PAT
    for t in range(n):
        if not close(pbt[t] - tax[t], pat[t]):
            errors.append(f"R4 (PBT-Tax=PAT) yr{t+1}: "
                          f"{pbt[t]:.2f}-{tax[t]:.2f}={pbt[t]-tax[t]:.2f} != PAT {pat[t]:.2f}")
    # R5: Assets = Liabilities + Equity
    for t in range(n):
        if not close(total_assets[t], total_liab[t] + total_equity[t]):
            errors.append(f"R5 (Assets=Liab+Equity) yr{t+1}: "
                          f"Assets {total_assets[t]:.2f} != {total_liab[t]:.2f}+{total_equity[t]:.2f}"
                          f"={total_liab[t]+total_equity[t]:.2f}")
    # R6: Operating + Investing + Financing = Net (Year 0..N)
    for t in range(n + 1):
        if not close(op_cf[t] + inv_cf[t] + fin_cf[t], net_cf[t]):
            errors.append(f"R6 (Op+Inv+Fin=Net) yr{t}: "
                          f"{op_cf[t]:.2f}+{inv_cf[t]:.2f}+{fin_cf[t]:.2f}"
                          f"={op_cf[t]+inv_cf[t]+fin_cf[t]:.2f} != Net {net_cf[t]:.2f}")
    # R7: cash_flow_series == net_cash_flow
    for t in range(n + 1):
        if not close(cf_series[t], net_cf[t]):
            errors.append(f"R7 (series==net) yr{t}: series {cf_series[t]:.2f} != net {net_cf[t]:.2f}")
    # R8: opening - principal = closing (every year)
    for t in range(n):
        if not close(opening[t] - principal[t], closing[t]):
            errors.append(f"R8 (opening-principal=closing) yr{t+1}: "
                          f"{opening[t]:.2f}-{principal[t]:.2f}={opening[t]-principal[t]:.2f} != closing {closing[t]:.2f}")
    # R9: total principal repaid ~= loan amount
    if not close(sum(principal), loan_amount):
        errors.append(f"R9 (sum principal ~= loan) sum {sum(principal):.2f} != loan {loan_amount:.2f}")
    # R10: Working Capital = Current Assets - Current Liabilities
    for t in range(n):
        if not close(ca[t] - cl[t], wc[t]):
            errors.append(f"R10 (WC=CA-CL) yr{t+1}: "
                          f"{ca[t]:.2f}-{cl[t]:.2f}={ca[t]-cl[t]:.2f} != WC {wc[t]:.2f}")
    # R11: DSCR = cash available / debt service
    for t in range(n):
        if abs(debt_service[t]) < 1e-9:
            warnings.append(f"R11 yr{t+1}: debt service is ~0; DSCR check skipped.")
            continue
        if not close(cash_avail[t] / debt_service[t], dscr[t]):
            errors.append(f"R11 (DSCR=cash/debt) yr{t+1}: "
                          f"{cash_avail[t]:.2f}/{debt_service[t]:.2f}={cash_avail[t]/debt_service[t]:.4f} != DSCR {dscr[t]:.4f}")
    # R12: Interest Coverage = EBIT / Interest
    for t in range(n):
        if abs(interest_total[t]) < 1e-9:
            warnings.append(f"R12 yr{t+1}: interest is ~0; interest-coverage check skipped.")
            continue
        if not close(ebit[t] / interest_total[t], icr[t]):
            errors.append(f"R12 (ICR=EBIT/Interest) yr{t+1}: "
                          f"{ebit[t]:.2f}/{interest_total[t]:.2f}={ebit[t]/interest_total[t]:.4f} != ICR {icr[t]:.4f}")
    # R13: Current Ratio = Current Assets / Current Liabilities
    for t in range(n):
        if abs(cl[t]) < 1e-9:
            warnings.append(f"R13 yr{t+1}: current liabilities ~0; current-ratio check skipped.")
            continue
        if not close(ca[t] / cl[t], curr_ratio[t]):
            errors.append(f"R13 (CurrRatio=CA/CL) yr{t+1}: "
                          f"{ca[t]:.2f}/{cl[t]:.2f}={ca[t]/cl[t]:.4f} != CurrRatio {curr_ratio[t]:.4f}")

    # R14: NPV evaluated at IRR ~= 0  (only if an IRR is provided)
    has_pos = any(cf > 0 for cf in cf_series)
    has_neg = any(cf < 0 for cf in cf_series)
    if irr is not None:
        npv_at_irr = sum(cf / ((1.0 + irr) ** t) for t, cf in enumerate(cf_series))
        if not close(npv_at_irr, 0.0):
            errors.append(f"R14 (NPV@IRR~=0): NPV at IRR={irr:.6f} is {npv_at_irr:.4f}, not ~0")
    # R15: IRR must be None when cash flows lack both signs
    if not (has_pos and has_neg):
        if irr is not None:
            errors.append(f"R15 (IRR None w/o sign change): cash flows lack both +/- but IRR={irr}")
    elif irr is None:
        warnings.append("R15: cash flows contain both signs but IRR is None (no real root found?).")

    return {"passed": len(errors) == 0, "warnings": warnings, "errors": errors}
