"""
test_cash_flow_builder_manual.py

Sanity-checks cash_flow_builder against a fully HAND-WORKED example — every year's
cash flow derived in comments, not compared against the code itself.

WORKED EXAMPLE (N = 5 years)
----------------------------
  assumptions:
      capital_expenditure    = 10,000,000   (Year-0 outflow)
      term_loan_amount       =  7,000,000   (Year-0 loan drawdown)
      promoters_capital      =  3,000,000   (Year-0 equity)
      initial_working_capital = 0

  profit_output.pat            = [1,000,000, 1,200,000, 1,400,000, 1,600,000, 1,800,000]
  depreciation.annual_deprec.  = [  800,000,   800,000,   800,000,   800,000,   800,000]
  working_capital.level        = [  500,000,   600,000,   700,000,   800,000,   900,000]
  loan_schedule.principal      = [1,400,000, 1,400,000, 1,400,000, 1,400,000, 1,400,000]

  Increase in Working Capital  (level[t] - level[t-1], year1 vs initial 0):
      y1 500,000-0=500,000 | y2 100,000 | y3 100,000 | y4 100,000 | y5 100,000

  OPERATING CF (Years 1-5) = PAT + Depreciation - Increase in WC:
      y1 = 1,000,000 + 800,000 - 500,000 = 1,300,000
      y2 = 1,200,000 + 800,000 - 100,000 = 1,900,000
      y3 = 1,400,000 + 800,000 - 100,000 = 2,100,000
      y4 = 1,600,000 + 800,000 - 100,000 = 2,300,000
      y5 = 1,800,000 + 800,000 - 100,000 = 2,500,000
      operating[Year 0] = 0
  => operating = [0, 1,300,000, 1,900,000, 2,100,000, 2,300,000, 2,500,000]

  INVESTING CF:
      Year 0 = -10,000,000 (capex);  Years 1-5 = 0
  => investing = [-10,000,000, 0, 0, 0, 0, 0]

  FINANCING CF:
      Year 0 = +7,000,000 + 3,000,000 = 10,000,000 (drawdown + equity)
      Years 1-5 = -1,400,000 each (principal only; interest already in PAT)
  => financing = [10,000,000, -1,400,000, -1,400,000, -1,400,000, -1,400,000, -1,400,000]

  NET CF = operating + investing + financing  (== cash_flow_series):
      Year 0 = 0 - 10,000,000 + 10,000,000 =        0
      Year 1 = 1,300,000 + 0 - 1,400,000   = -100,000
      Year 2 = 1,900,000 - 1,400,000       =  500,000
      Year 3 = 2,100,000 - 1,400,000       =  700,000
      Year 4 = 2,300,000 - 1,400,000       =  900,000
      Year 5 = 2,500,000 - 1,400,000       = 1,100,000
  => cash_flow_series = [0, -100,000, 500,000, 700,000, 900,000, 1,100,000]

  Totals: sum(net)=3,100,000 ; sum(operating)=10,100,000 ;
          sum(investing)=-10,000,000 ; sum(financing)=3,000,000
          (10,100,000 - 10,000,000 + 3,000,000 = 3,100,000  -> consistent)

Run from backend/:
    python financial_engine/calculations/generic/test_cash_flow_builder_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.calculations.generic.cash_flow_builder import (  # noqa: E402
    build_cash_flow_series,
)

EXPECT = {
    "cash_flow_series":    [0, -100_000, 500_000, 700_000, 900_000, 1_100_000],
    "operating_cash_flow": [0, 1_300_000, 1_900_000, 2_100_000, 2_300_000, 2_500_000],
    "investing_cash_flow": [-10_000_000, 0, 0, 0, 0, 0],
    "financing_cash_flow": [10_000_000, -1_400_000, -1_400_000, -1_400_000, -1_400_000, -1_400_000],
}

failures = []


def check_series(label, got, expected):
    ok = len(got) == len(expected) and all(abs(g - e) < 1e-6 for g, e in zip(got, expected))
    if not ok:
        failures.append((label, got, expected))
    print(f"  {'OK ' if ok else 'FAIL'} {label:<22} {['{:,.0f}'.format(x) for x in got]}")


def main():
    assumptions = {
        "capital_expenditure": 10_000_000,
        "term_loan_amount": 7_000_000,
        "promoters_capital": 3_000_000,
        "initial_working_capital": 0,
    }
    profit = {"pat": [1_000_000, 1_200_000, 1_400_000, 1_600_000, 1_800_000]}
    deprec = {"annual_depreciation": [800_000] * 5}
    wc = {"working_capital": [500_000, 600_000, 700_000, 800_000, 900_000]}
    loan = {"principal": [1_400_000] * 5}

    res = build_cash_flow_series(assumptions, profit, deprec, wc, loan)

    print("=" * 84)
    print("YEARLY CASH FLOW  —  Python vs hand-worked values")
    print("=" * 84)
    print(f"  {'':22} {'Yr0':>11}{'Yr1':>12}{'Yr2':>12}{'Yr3':>12}{'Yr4':>12}{'Yr5':>12}")
    for key in ("operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
                "net_cash_flow", "cash_flow_series"):
        row = res[key]
        print(f"  {key:<22}" + "".join(f"{v:>12,.0f}" for v in row))

    print("\n  checks:")
    for key, exp in EXPECT.items():
        check_series(key, res[key], exp)
    # net_cash_flow must equal cash_flow_series exactly
    same = res["net_cash_flow"] == res["cash_flow_series"]
    print(f"  {'OK ' if same else 'FAIL'} net_cash_flow == cash_flow_series")
    if not same:
        failures.append(("net==series", res["net_cash_flow"], res["cash_flow_series"]))

    print("\n  totals:")
    for key in ("cash_flow_series", "operating_cash_flow", "investing_cash_flow",
                "financing_cash_flow"):
        print(f"    sum({key}) = {sum(res[key]):>14,.0f}")
    exp_totals = {"cash_flow_series": 3_100_000, "operating_cash_flow": 10_100_000,
                  "investing_cash_flow": -10_000_000, "financing_cash_flow": 3_000_000}
    for key, exp in exp_totals.items():
        ok = abs(sum(res[key]) - exp) < 1e-6
        if not ok:
            failures.append((f"total {key}", sum(res[key]), exp))

    print("\n" + "=" * 84)
    print("VALIDATION (invalid inputs must raise ValueError)")
    print("=" * 84)
    good = (assumptions, profit, deprec, wc, loan)
    cases = [
        ("profit_output not a dict",
         lambda: build_cash_flow_series(assumptions, [], deprec, wc, loan)),
        ("assumptions not a dict",
         lambda: build_cash_flow_series("x", profit, deprec, wc, loan)),
        ("missing pat key",
         lambda: build_cash_flow_series(assumptions, {}, deprec, wc, loan)),
        ("series lengths differ",
         lambda: build_cash_flow_series(assumptions, {"pat": [1, 2, 3]}, deprec, wc, loan)),
        ("missing capex + components",
         lambda: build_cash_flow_series({"term_loan_amount": 1, "promoters_capital": 1},
                                        profit, deprec, wc, loan)),
        ("missing term_loan_amount",
         lambda: build_cash_flow_series({"capital_expenditure": 1, "promoters_capital": 1},
                                        profit, deprec, wc, loan)),
    ]
    for label, fn in cases:
        try:
            fn()
            print(f"  FAIL {label:<30} -> NO ERROR")
            failures.append((f"validation {label}", 1, 0))
        except ValueError as e:
            print(f"  OK   {label:<30} -> ValueError: {str(e).split(':',1)[1].strip()[:40]}")

    print("\n" + "=" * 84)
    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for lbl, got, exp in failures:
            print(f"   {lbl}: got={got} expected={exp}")
        raise AssertionError("cash-flow results disagree with hand-worked values")
    print("PASSED — every year's operating / investing / financing / net cash flow")
    print("matches the hand-worked values; totals reconcile; validation raises correctly.")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
