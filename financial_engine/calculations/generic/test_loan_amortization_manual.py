"""
test_loan_amortization_manual.py

Sanity-checks loan_amortization_calc against HAND-COMPUTED values, not against itself.

WORKED EXAMPLE (EMI with moratorium)
------------------------------------
  loan_amount        = 10,000,000
  annual rate        = 0.12 (12%)
  tenure             = 5 years  -> 60 months
  moratorium         = 6 months (principal holiday; interest still paid)
  repayment_type     = emi

  monthly interest rate      = 0.12 / 12 = 0.01  (1% per month)
  repayment months           = 60 - 6 = 54  (principal amortised over these)

  EMI formula (level payment, reducing balance):
      EMI = P * r * (1+r)^n / ((1+r)^n - 1)
      P = 10,000,000,  r = 0.01,  n = 54
      (1.01)^54 ~= 1.7114105
      EMI = 10,000,000 * 0.01 * 1.7114105 / (1.7114105 - 1)
          = 171,141.05 / 0.7114105
          ~= 240,565.83

  Month 1 (inside moratorium):
      interest = 10,000,000 * 0.01 = 100,000
      principal = 0                       (moratorium)
      closing balance = 10,000,000        (unchanged)

  Month 7 (first EMI month):
      opening   = 10,000,000
      interest  = 100,000
      principal = EMI - interest ~= 240,565.83 - 100,000 = 140,565.83
      closing   ~= 10,000,000 - 140,565.83 = 9,859,434.17

  Final month (60): closing balance must be exactly 0.00
  total_principal must equal the loan exactly: 10,000,000.00

Run from backend/:
    python financial_engine/calculations/generic/test_loan_amortization_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.calculations.generic.loan_amortization_calc import (  # noqa: E402
    calculate_loan_schedule,
)

failures = []


def approx(got, expected, tol, label):
    ok = got is not None and abs(got - expected) <= tol
    if not ok:
        failures.append((label, got, expected, tol))
    print(f"  {'OK ' if ok else 'FAIL'} {label:<44} python={got:>14,.2f}  expected~={expected:>14,.2f}")


def main():
    print("=" * 78)
    print("1. EMI + 6-MONTH MORATORIUM  (10,000,000 @ 12% / 5yr)")
    print("=" * 78)
    r = calculate_loan_schedule({}, 10_000_000, 0.12, 5, moratorium_months=6, repayment_type="emi")
    m = r["monthly_schedule"]

    # Month 1 (moratorium): interest 100,000, principal 0, balance unchanged
    approx(m[0]["interest"], 100_000.00, 0.01, "month 1 interest (moratorium)")
    approx(m[0]["principal"], 0.00, 0.001, "month 1 principal (moratorium=0)")
    approx(m[0]["closing_balance"], 10_000_000.00, 0.01, "month 1 closing (unchanged)")

    # Month 7 (first EMI): interest 100,000, principal ~140,568.7
    approx(m[6]["interest"], 100_000.00, 0.01, "month 7 interest")
    approx(m[6]["emi"], 240_565.83, 0.05, "month 7 EMI (level payment)")
    approx(m[6]["principal"], 140_565.83, 0.05, "month 7 principal")
    approx(m[6]["closing_balance"], 9_859_434.17, 0.05, "month 7 closing")

    # Final month exactly zero; total principal == loan
    print(f"\n  final month closing_balance = {m[-1]['closing_balance']}  (must be 0.00)")
    if m[-1]["closing_balance"] != 0.0:
        failures.append(("final closing == 0", m[-1]["closing_balance"], 0.0, 0.0))
    approx(r["total_principal"], 10_000_000.00, 0.01, "total_principal == loan")
    print(f"  months in schedule = {len(m)} (expect 60);  EMI months carry level payment ~240,565.83")
    print(f"  total_interest = {r['total_interest']:,.2f}   total_payment = {r['total_payment']:,.2f}")
    print(f"  effective_interest_rate = {r['effective_interest_rate']}  "
          f"(EAR = 1.01^12 - 1 = 0.126825)")
    approx(r["effective_interest_rate"], 0.126825, 1e-5, "effective annual rate")

    print("\n" + "=" * 78)
    print("2. EQUAL-PRINCIPAL  (1,200,000 @ 10% / 1yr, no moratorium)")
    print("=" * 78)
    # principal/month = 1,200,000 / 12 = 100,000 (constant)
    # month 1: interest = 1,200,000 * 0.10/12 = 10,000; emi = 110,000; closing 1,100,000
    r2 = calculate_loan_schedule({}, 1_200_000, 0.10, 1, repayment_type="equal_principal")
    m2 = r2["monthly_schedule"]
    approx(m2[0]["principal"], 100_000.00, 0.01, "month 1 principal (constant)")
    approx(m2[0]["interest"], 10_000.00, 0.01, "month 1 interest")
    approx(m2[0]["emi"], 110_000.00, 0.01, "month 1 payment")
    approx(m2[1]["principal"], 100_000.00, 0.01, "month 2 principal (still constant)")
    approx(m2[1]["interest"], 9_166.67, 0.01, "month 2 interest (reduced)")
    print(f"  final closing = {m2[-1]['closing_balance']} (0.00); total_principal = {r2['total_principal']:,.2f}")
    approx(r2["total_principal"], 1_200_000.00, 0.01, "total_principal == loan")

    print("\n" + "=" * 78)
    print("3. ZERO-INTEREST LOAN  (1,200,000 @ 0% / 1yr, EMI)")
    print("=" * 78)
    # EMI = 1,200,000 / 12 = 100,000; interest 0 every month
    r3 = calculate_loan_schedule({}, 1_200_000, 0.0, 1, repayment_type="emi")
    m3 = r3["monthly_schedule"]
    approx(m3[0]["emi"], 100_000.00, 0.01, "month 1 EMI (= principal)")
    approx(m3[0]["interest"], 0.00, 0.001, "month 1 interest (zero)")
    approx(r3["total_interest"], 0.00, 0.001, "total_interest (zero)")
    approx(r3["effective_interest_rate"], 0.0, 1e-9, "effective rate (zero)")
    print(f"  final closing = {m3[-1]['closing_balance']} (0.00)")

    print("\n" + "=" * 78)
    print("4. MORATORIUM HANDLING  (principal 0, balance flat, interest > 0 during holiday)")
    print("=" * 78)
    hol = m[:6]
    all_flat = all(row["principal"] == 0.0 and row["closing_balance"] == 10_000_000.00
                   and row["interest"] > 0 for row in hol)
    print(f"  months 1-6: principal all 0, closing all 10,000,000, interest all > 0: {all_flat}")
    if not all_flat:
        failures.append(("moratorium months flat", 0, 1, 0))

    print("\n" + "=" * 78)
    print("5. FINAL BALANCE EXACTLY ZERO across scenarios")
    print("=" * 78)
    for lbl, res in [("emi+moratorium", r), ("equal_principal", r2), ("zero-interest", r3)]:
        cb = res["monthly_schedule"][-1]["closing_balance"]
        print(f"  {lbl:<20} final closing_balance = {cb}  ({'OK' if cb == 0.0 else 'FAIL'})")
        if cb != 0.0:
            failures.append((f"{lbl} final zero", cb, 0.0, 0.0))

    print("\n" + "=" * 78)
    print("6. VALIDATION (invalid inputs must raise ValueError)")
    print("=" * 78)
    cases = [
        ("percentage-form rate (12)", lambda: calculate_loan_schedule({}, 1_000_000, 12, 5)),
        ("negative loan amount",      lambda: calculate_loan_schedule({}, -1_000_000, 0.12, 5)),
        ("zero loan amount",          lambda: calculate_loan_schedule({}, 0, 0.12, 5)),
        ("negative interest",         lambda: calculate_loan_schedule({}, 1_000_000, -0.05, 5)),
        ("tenure 0",                  lambda: calculate_loan_schedule({}, 1_000_000, 0.12, 0)),
        ("moratorium negative",       lambda: calculate_loan_schedule({}, 1_000_000, 0.12, 5, -1)),
        ("unsupported repayment_type",lambda: calculate_loan_schedule({}, 1_000_000, 0.12, 5, 0, "balloon")),
        ("assumptions not a dict",    lambda: calculate_loan_schedule([], 1_000_000, 0.12, 5)),
        ("moratorium >= tenure",      lambda: calculate_loan_schedule({}, 1_000_000, 0.12, 1, 12)),
    ]
    for label, fn in cases:
        try:
            fn()
            print(f"  FAIL {label:<32} -> NO ERROR")
            failures.append((f"validation {label}", 1, 0, 0))
        except ValueError as e:
            print(f"  OK   {label:<32} -> ValueError: {str(e).split(':',1)[1].strip()[:44]}")

    print("\n" + "=" * 78)
    if failures:
        print(f"FAILED — {len(failures)} check(s):")
        for lbl, got, exp, tol in failures:
            print(f"   {lbl}: got={got} expected={exp}")
        raise AssertionError("loan amortization results disagree with hand-computed values")
    print("PASSED — EMI/moratorium, equal-principal, zero-interest all match hand-computed")
    print("values; final balance is exactly zero; all invalid inputs raise ValueError.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
