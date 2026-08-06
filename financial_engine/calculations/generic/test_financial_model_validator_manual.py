"""
test_financial_model_validator_manual.py

Exercises financial_model_validator with ONE fully self-consistent dataset that must
pass all 15 rules, and several INTENTIONALLY BROKEN datasets that must each trip a
specific rule. Prints a per-rule PASS/FAIL report and a final summary.

CONSISTENT DATASET (N = 5), built so every relationship holds exactly
--------------------------------------------------------------------
  Revenue   = [10.0, 11.0, 12.0, 13.0, 14.0] (M)
  Expenses  = [ 7.0,  7.5,  8.0,  8.5,  9.0]
  EBITDA    = Rev - Exp        = [3.0, 3.5, 4.0, 4.5, 5.0]
  Deprec    = 0.8 each year
  EBIT      = EBITDA - Dep     = [2.2, 2.7, 3.2, 3.7, 4.2]
  Loan 7.0M, equal principal 1.4M/yr, 10% reducing:
     opening   = [7.0, 5.6, 4.2, 2.8, 1.4]
     interest  = [0.7, 0.56, 0.42, 0.28, 0.14]
     principal = 1.4 each ; closing = opening-principal = [5.6,4.2,2.8,1.4,0]
     sum principal = 7.0 = loan
  PBT = EBIT - interest        = [1.5, 2.14, 2.78, 3.42, 4.06]
  Tax = 25% * PBT              = [0.375, 0.535, 0.695, 0.855, 1.015]
  PAT = PBT - Tax              = [1.125, 1.605, 2.085, 2.565, 3.045]
  Working capital: CA=[2.0,2.2,2.4,2.6,2.8] CL=[0.8,0.85,0.9,0.95,1.0]
     WC = CA-CL                = [1.2, 1.35, 1.5, 1.65, 1.8]
  Balance sheet:
     equity = 3.0 promoter + cumulative PAT = [4.125, 5.73, 7.815, 10.38, 13.425]
     liab   = loan closing + CL             = [6.4, 5.05, 3.7, 2.35, 1.0]
     assets = liab + equity                 = [10.525, 10.78, 11.515, 12.73, 14.425]
  Ratios:
     DSCR = (PAT+Dep+interest)/(principal+interest)
     ICR  = EBIT / interest
     CurrRatio = CA / CL
  Cash flow (Year0..5): capex 10.0, drawdown 7.0, equity 3.0, initial WC 0
     operating = PAT + Dep - dWC ; investing = [-10,0,0,0,0,0]
     financing = [10,-1.4,-1.4,-1.4,-1.4,-1.4]
     net = op+inv+fin  -> Year0 = 0
  IRR/NPV: computed from the net cash-flow series (has both signs -> real IRR).

All amounts below are in whole rupees (the M figures above * 1,000,000).

Run from backend/:
    python financial_engine/calculations/generic/test_financial_model_validator_manual.py
"""

import copy
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.calculations.generic.financial_model_validator import (  # noqa: E402
    validate_financial_model,
)
# Only used to GENERATE a consistent irr for the sample data (the validator checks it
# independently by recomputing NPV at that irr).
from financial_engine.calculations.generic.irr_npv_calc import _irr, npv  # noqa: E402

M = 1_000_000


def build_consistent():
    revenue = [10 * M, 11 * M, 12 * M, 13 * M, 14 * M]
    expenses = [7 * M, 7.5 * M, 8 * M, 8.5 * M, 9 * M]
    ebitda = [r - e for r, e in zip(revenue, expenses)]
    dep = [0.8 * M] * 5
    ebit = [a - d for a, d in zip(ebitda, dep)]
    opening = [7 * M, 5.6 * M, 4.2 * M, 2.8 * M, 1.4 * M]
    interest = [0.7 * M, 0.56 * M, 0.42 * M, 0.28 * M, 0.14 * M]
    principal = [1.4 * M] * 5
    closing = [o - p for o, p in zip(opening, principal)]
    pbt = [e - i for e, i in zip(ebit, interest)]
    tax = [0.25 * p for p in pbt]
    pat = [p - t for p, t in zip(pbt, tax)]
    ca = [2 * M, 2.2 * M, 2.4 * M, 2.6 * M, 2.8 * M]
    cl = [0.8 * M, 0.85 * M, 0.9 * M, 0.95 * M, 1 * M]
    wc = [a - l for a, l in zip(ca, cl)]

    equity, run = [], 3 * M
    for p in pat:
        run += p
        equity.append(run)
    liab = [c + l for c, l in zip(closing, cl)]
    assets = [l + e for l, e in zip(liab, equity)]

    # cash flow
    d_wc, prev = [], 0.0
    for level in wc:
        d_wc.append(level - prev); prev = level
    operating = [0.0] + [pat[t] + dep[t] - d_wc[t] for t in range(5)]
    investing = [-10 * M, 0, 0, 0, 0, 0]
    financing = [7 * M + 3 * M] + [-p for p in principal]
    net = [o + i + f for o, i, f in zip(operating, investing, financing)]

    # ratios
    cash_avail = [pat[t] + dep[t] + interest[t] for t in range(5)]
    debt_service = [principal[t] + interest[t] for t in range(5)]
    dscr = [cash_avail[t] / debt_service[t] for t in range(5)]
    icr = [ebit[t] / interest[t] for t in range(5)]
    curr = [ca[t] / cl[t] for t in range(5)]

    irr = _irr(net)
    return {
        "assumptions": {"term_loan_amount": 7 * M, "promoters_capital": 3 * M},
        "profit_output": {"revenue": revenue, "expenses": expenses, "ebitda": ebitda,
                          "ebit": ebit, "pbt": pbt, "tax": tax, "pat": pat},
        "depreciation_output": {"annual_depreciation": dep},
        "working_capital_output": {"current_assets": ca, "current_liabilities": cl,
                                   "working_capital": wc, "wc_interest_annual": [0.0] * 5},
        "loan_schedule_output": {"opening_balance": opening, "interest": interest,
                                 "principal": principal, "closing_balance": closing},
        "cash_flow_output": {"operating_cash_flow": operating, "investing_cash_flow": investing,
                             "financing_cash_flow": financing, "net_cash_flow": net,
                             "cash_flow_series": list(net)},
        "balance_sheet_output": {"total_assets": assets, "total_liabilities": liab,
                                 "total_equity": equity},
        "ratio_output": {"dscr": dscr, "interest_coverage": icr, "current_ratio": curr,
                         "cash_available_for_debt_service": cash_avail,
                         "total_debt_obligation": debt_service},
        "irr_npv_output": {"irr": irr, "npv": npv(0.12, net)},
    }


def run(ds):
    return validate_financial_model(
        ds["assumptions"], ds["profit_output"], ds["depreciation_output"],
        ds["working_capital_output"], ds["loan_schedule_output"], ds["cash_flow_output"],
        ds["balance_sheet_output"], ds["ratio_output"], ds["irr_npv_output"])


def broken(mutate):
    ds = copy.deepcopy(base)
    mutate(ds)
    return ds


def main():
    global base
    base = build_consistent()

    print("=" * 82)
    print("CONSISTENT DATASET  —  must pass all 15 rules")
    print("=" * 82)
    res = run(base)
    RULES = {
        "R1": "Revenue - Expenses = EBITDA", "R2": "EBITDA - Depreciation = EBIT",
        "R3": "EBIT - Interest = PBT", "R4": "PBT - Tax = PAT",
        "R5": "Assets = Liabilities + Equity", "R6": "Op+Inv+Fin = Net cash flow",
        "R7": "cash_flow_series = net_cash_flow", "R8": "opening - principal = closing",
        "R9": "sum principal ~= loan", "R10": "WC = CA - CL",
        "R11": "DSCR = cash / debt service", "R12": "Interest coverage = EBIT / interest",
        "R13": "Current ratio = CA / CL", "R14": "NPV at IRR ~= 0",
        "R15": "IRR None w/o sign change",
    }
    fired = {r for r in RULES if any(e.startswith(r + " ") or e.startswith(r + ":") for e in res["errors"])}
    for r, desc in RULES.items():
        print(f"  {'PASS' if r not in fired else 'FAIL'}  {r:<4} {desc}")
    print(f"\n  passed={res['passed']}  errors={len(res['errors'])}  warnings={len(res['warnings'])}")
    for w in res["warnings"]:
        print(f"    warn: {w}")
    ok_consistent = res["passed"] and not res["errors"]
    print(f"  --> consistent dataset {'OK' if ok_consistent else 'FAILED (should have passed!)'}")

    print("\n" + "=" * 82)
    print("BROKEN DATASETS  —  each must trip its target rule")
    print("=" * 82)

    def set_bs(ds):      ds["balance_sheet_output"]["total_assets"][2] += 999_999
    def set_pat(ds):     ds["profit_output"]["pat"][1] += 500_000
    def set_dscr(ds):    ds["ratio_output"]["dscr"][0] = 9.99
    def set_loan(ds):    ds["loan_schedule_output"]["closing_balance"][2] += 250_000
    def set_cf(ds):      ds["cash_flow_output"]["cash_flow_series"][3] += 111_111
    def set_ebitda(ds):  ds["profit_output"]["ebitda"][4] -= 700_000
    def set_wc(ds):      ds["working_capital_output"]["working_capital"][0] += 300_000
    def set_irr(ds):     ds["irr_npv_output"]["irr"] = 0.5  # wrong -> NPV@0.5 != 0

    scenarios = [
        ("Balance-sheet mismatch",     set_bs,     "R5"),
        ("Wrong PAT",                  set_pat,    "R4"),
        ("Incorrect DSCR",             set_dscr,   "R11"),
        ("Loan schedule mismatch",     set_loan,   "R8"),
        ("Invalid cash-flow reconcile",set_cf,     "R7"),
        ("Wrong EBITDA",               set_ebitda, "R1"),
        ("Working-capital identity",   set_wc,     "R10"),
        ("Wrong IRR (NPV@IRR != 0)",   set_irr,    "R14"),
    ]
    all_ok = ok_consistent
    for label, mut, target in scenarios:
        res = run(broken(mut))
        fired = {e.split()[0].rstrip(":") for e in res["errors"]}
        hit = target in fired
        all_ok = all_ok and hit and not res["passed"]
        print(f"  {'OK  ' if hit and not res['passed'] else 'FAIL'} {label:<30} "
              f"expected {target:<4} -> passed={res['passed']}, rules_fired={sorted(fired)}")

    print("\n" + "=" * 82)
    print("MALFORMED INPUTS  —  must raise ValueError (not return errors)")
    print("=" * 82)
    mal = [
        ("profit_output not a dict",
         lambda: validate_financial_model(base["assumptions"], [], base["depreciation_output"],
                 base["working_capital_output"], base["loan_schedule_output"],
                 base["cash_flow_output"], base["balance_sheet_output"],
                 base["ratio_output"], base["irr_npv_output"])),
        ("missing pat key",
         lambda: validate_financial_model(base["assumptions"], {"revenue": [1]*5},
                 base["depreciation_output"], base["working_capital_output"],
                 base["loan_schedule_output"], base["cash_flow_output"],
                 base["balance_sheet_output"], base["ratio_output"], base["irr_npv_output"])),
        ("series length mismatch",
         lambda: (lambda ds: validate_financial_model(ds["assumptions"], ds["profit_output"],
                 ds["depreciation_output"], ds["working_capital_output"],
                 ds["loan_schedule_output"], ds["cash_flow_output"],
                 ds["balance_sheet_output"], ds["ratio_output"], ds["irr_npv_output"]))(
                    (lambda d: (d["loan_schedule_output"].__setitem__("principal", [1, 2, 3]) or d))(copy.deepcopy(base)))),
    ]
    mal_ok = True
    for label, fn in mal:
        try:
            fn(); print(f"  FAIL {label:<28} -> NO ERROR"); mal_ok = False
        except ValueError as e:
            print(f"  OK   {label:<28} -> ValueError: {str(e).split(':',1)[1].strip()[:44]}")

    print("\n" + "=" * 82)
    ok = all_ok and mal_ok
    print("FINAL SUMMARY:", "ALL VALIDATIONS BEHAVED AS EXPECTED" if ok else "SOME CHECKS FAILED")
    print("=" * 82)
    if not ok:
        raise AssertionError("validator did not behave as specified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
