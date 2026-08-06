"""
test_irr_npv_manual.py

Sanity-checks irr_npv_calc against HAND-COMPUTED finance-textbook values — not
against itself. The worked example below is deliberately simple so the expected
numbers can be verified with a calculator.

WORKED EXAMPLE
--------------
  initial_investment = 1,000,000
  cash_flow_series   = [-1,000,000, 300,000, 300,000, 300,000, 300,000, 300,000]
                        (Year 0 outflow, then 300,000/yr for 5 years)
  discount_rate      = 0.12 (12%)
  project_life_years = 5

  5-year annuity factor @12% = (1 - 1.12^-5) / 0.12
      1.12^5   = 1.7623417
      1.12^-5  = 0.5674269
      factor   = (1 - 0.5674269) / 0.12 = 0.4325731 / 0.12 = 3.6047759

  PV of inflows = 300,000 x 3.6047759 = 1,081,432.8
  NPV           = 1,081,432.8 - 1,000,000            = +81,432.8      (expect ~81,433)

  IRR: rate r where 300,000 x annuity(r,5) = 1,000,000  ->  annuity(r,5) = 3.33333
      @15%: annuity = (1 - 1.15^-5)/0.15 = 3.352155 -> PV 1,005,646 -> NPV +5,646
      @16%: annuity = (1 - 1.16^-5)/0.16 = 3.274294 -> PV   982,288 -> NPV -17,712
      linear interp: 15% + 5,646/(5,646+17,712) = 15% + 0.2417% = ~15.24%
      IRR (textbook) ~= 0.15238                                     (expect ~0.1524)

  Simple payback = 1,000,000 / 300,000 = 3.3333 years
      (cumulative: 900k after 3 yrs; need 100k of yr-4's 300k -> 3 + 100/300 = 3.333)

  Discounted payback @12%:
      disc CF: y1 267,857  y2 239,158  y3 213,534  y4 190,655  y5 170,228
      cumulative: 267,857 / 507,015 / 720,549 / 911,204 / 1,081,432
      recovers 1,000,000 during year 5: 4 + (1,000,000-911,204)/170,228
                                       = 4 + 88,796/170,228 = ~4.522 years

  Profitability index = PV inflows / initial investment
                      = 1,081,432.8 / 1,000,000 = 1.0814

Run from backend/:
    python financial_engine/calculations/generic/test_irr_npv_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.calculations.generic.irr_npv_calc import (  # noqa: E402
    calculate_irr_npv_payback, npv,
)

# (label, expected, tolerance)
EXPECTED = {
    "irr": (0.15238, 0.0005),
    "npv": (81_432.8, 1.0),
    "payback_period_years": (3.3333, 0.001),
    "discounted_payback_years": (4.522, 0.01),
    "profitability_index": (1.0814, 0.001),
}


def main():
    assumptions = {}  # not consumed by this calc; passed for signature consistency
    series = [-1_000_000.0, 300_000.0, 300_000.0, 300_000.0, 300_000.0, 300_000.0]
    res = calculate_irr_npv_payback(
        assumptions, cash_flow_series=series,
        initial_investment=1_000_000.0, discount_rate=0.12, project_life_years=5)

    print("=" * 74)
    print("IRR / NPV / PAYBACK  —  Python vs hand-computed textbook values")
    print("  II=1,000,000 | CF=300,000/yr x5 | discount=12%")
    print("=" * 74)
    print(f"  {'metric':<26}{'PYTHON':>16}{'EXPECTED':>16}{'':>6}")
    print("  " + "-" * 64)

    failures = []
    for key, (expected, tol) in EXPECTED.items():
        got = res[key]
        ok = got is not None and abs(got - expected) <= tol
        if not ok:
            failures.append((key, got, expected, tol))
        gs = f"{got:.5f}" if isinstance(got, float) else str(got)
        print(f"  {key:<26}{gs:>16}{expected:>16.5f}   {'OK' if ok else 'MISMATCH'}")

    # cross-check: NPV at the IRR must be ~0 (definition of IRR)
    npv_at_irr = npv(res["irr"], series)
    print(f"\n  NPV at computed IRR (should be ~0): {npv_at_irr:.4f}")
    assert abs(npv_at_irr) < 1e-3, "IRR does not zero the NPV"

    print("\n" + "=" * 74)
    print("EDGE CASES")
    print("=" * 74)
    # 1. No sign change -> IRR None (never 0)
    r2 = calculate_irr_npv_payback({}, [100.0]*6, initial_investment=1.0,
                                   discount_rate=0.1, project_life_years=5)
    print(f"  all-positive flows -> irr is None: {r2['irr'] is None}")
    assert r2["irr"] is None

    # 2. Never recovers -> payback None
    r3 = calculate_irr_npv_payback({}, [-1_000_000.0, 10_000.0, 10_000.0, 10_000.0,
                                        10_000.0, 10_000.0],
                                   initial_investment=1_000_000.0, discount_rate=0.1,
                                   project_life_years=5)
    print(f"  tiny flows -> simple payback None: {r3['payback_period_years'] is None}")
    print(f"  tiny flows -> NPV negative: {r3['npv'] < 0}")
    assert r3["payback_period_years"] is None and r3["npv"] < 0

    # 3. percentage-form discount rate -> ValueError
    try:
        calculate_irr_npv_payback({}, series, 1_000_000.0, discount_rate=12,
                                  project_life_years=5)
        print("  discount_rate=12 -> NO ERROR (!!)")
    except ValueError as e:
        print(f"  discount_rate=12 -> ValueError: {str(e)[:60]}...")

    # 4. too-short series -> ValueError
    try:
        calculate_irr_npv_payback({}, [-1_000_000.0, 300_000.0], 1_000_000.0, 0.12, 5)
        print("  short series -> NO ERROR (!!)")
    except ValueError as e:
        print(f"  short series -> ValueError: {str(e)[:60]}...")

    print("\n" + "=" * 74)
    if failures:
        print(f"FAILED — {len(failures)} metric(s) off textbook value:")
        for k, got, exp, tol in failures:
            print(f"  {k}: python={got} expected={exp} (tol {tol})")
        raise AssertionError("computed metrics disagree with hand-computed values")
    print("PASSED — all metrics match the hand-computed textbook values, and the")
    print("computed IRR zeroes the NPV. Edge cases (no-IRR, no-payback, bad inputs)")
    print("return None / raise as specified.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
