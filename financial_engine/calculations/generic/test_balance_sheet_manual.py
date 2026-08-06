"""
test_balance_sheet_manual.py

Parity check for the projected balance sheet against the real post-fix workbooks in
generated_reports/, recalculated by LibreOffice.

Chains every previously-proven calculator (revenue, expenses, depreciation, loan,
working capital, profit) into balance_sheet_calc, so this also proves the modules
compose correctly through to the balance sheet.

Ground truth = Form_III_BalanceSheet rows 6-22, columns C..G (Years 1..5).

Run from backend/:
    python financial_engine/calculations/generic/test_balance_sheet_manual.py
"""

import glob
import os
import sys
from pathlib import Path

from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.calculations.generic.test_loan_depreciation_wc_manual import (  # noqa: E402
    read_assumptions, annual_row,
)
from financial_engine.calculations.generic.test_profit_manual import build_pl  # noqa: E402
from financial_engine.calculations.generic.revenue_calc import (  # noqa: E402
    calculate_monthly_production, calculate_monthly_revenue, yearly_totals,
)
from financial_engine.calculations.generic.expense_calc import (  # noqa: E402
    calculate_monthly_variable_costs, calculate_monthly_fixed_costs,
)
from financial_engine.calculations.generic.depreciation_calc import (  # noqa: E402
    calculate_annual_depreciation,
)
from financial_engine.calculations.generic.working_capital_calc import (  # noqa: E402
    calculate_working_capital,
)
from financial_engine.calculations.generic.balance_sheet_calc import (  # noqa: E402
    calculate_balance_sheet,
)

TOLERANCE = 0.005  # 0.5%

# Balance-sheet row -> the key returned by calculate_balance_sheet
BS_ROWS = [
    ("Promoters' equity", 6, "promoters_equity"),
    ("Reserves & surplus", 7, "reserves_surplus"),
    ("Net Worth", 8, "net_worth"),
    ("Term loan (closing)", 9, "term_loan_closing"),
    ("WC bank borrowing", 10, "wc_borrowing"),
    ("Sundry creditors", 11, "sundry_creditors"),
    ("Other current liab.", 12, "other_current_liabilities"),
    ("TOTAL LIABILITIES", 13, "total_liabilities"),
    ("Gross fixed assets", 15, "gross_fixed_assets"),
    ("Accumulated deprec.", 16, "accumulated_depreciation"),
    ("Net fixed assets", 17, "net_fixed_assets"),
    ("Inventory", 18, "inventory"),
    ("Sundry debtors", 19, "debtors"),
    ("Cash (balancing)", 20, "cash_balancing_figure"),
    ("TOTAL ASSETS", 21, "total_assets"),
    ("Check (Liab-Assets)", 22, "balance_check"),
]


def build_balance_sheet(wb, a):
    """Chain all calculators to produce the balance sheet for this workbook."""
    production = calculate_monthly_production(a)
    revenue = calculate_monthly_revenue(a, production)
    var = calculate_monthly_variable_costs(a, production)
    fix = calculate_monthly_fixed_costs(a, revenue)
    dep_a = calculate_annual_depreciation(a)

    cop = [c1 + c2 + w + ov + fo + rmn + dep_a for c1, c2, w, ov, fo, rmn in zip(
        yearly_totals(var["cost1"]), yearly_totals(var["cost2"]),
        yearly_totals(fix["wages"]), yearly_totals(var["other_variable"]),
        yearly_totals(fix["factory_overheads"]), yearly_totals(fix["repairs_maintenance"]))]
    wc = calculate_working_capital(
        a,
        annual_revenue=yearly_totals(revenue),
        annual_cost_of_production_ex_wc_interest=cop,
        wc_interest_rate=a["interest_rate_wc"],
        annual_purchases=yearly_totals(var["cost1"]),
    )

    pl = build_pl(wb, a)                         # annual PAT (corrected annual-PBT tax)
    annual_dep_total = [dep_a] * 5               # flat annual depreciation

    return calculate_balance_sheet(
        a,
        annual_pat=pl["pat"],
        annual_depreciation_total=annual_dep_total,
        wc_data=wc,
    )


def main():
    files = sorted(p for p in glob.glob(str(BACKEND_DIR / "generated_reports" / "*.xlsx"))
                   if not os.path.basename(p).startswith("~$"))
    if not files:
        print("[!] No workbooks in generated_reports/.")
        return 1

    failures = []
    overall = 0.0
    any_negative_cash = False

    for path in files:
        wb = load_workbook(path, data_only=True)
        a = read_assumptions(wb)
        bs = build_balance_sheet(wb, a)

        print("=" * 116)
        print(f"{os.path.basename(path)}")
        print("=" * 116)
        print(f"  {'Line':<24}{'Yr1':>17}{'Yr2':>17}{'Yr3':>17}{'Yr4':>17}{'Yr5':>17}   max%")
        print("  " + "-" * 112)

        for label, row, key in BS_ROWS:
            py = bs[key]
            xl = annual_row(wb, "Form_III_BalanceSheet", row)
            pcts = []
            for p, e in zip(py, xl):
                denom = abs(e) if abs(e) > 1e-9 else (abs(p) if abs(p) > 1e-9 else 1.0)
                pcts.append(abs(p - e) / denom)
            worst = max(pcts)
            overall = max(overall, worst)
            if worst > TOLERANCE:
                failures.append((os.path.basename(path), label, py, xl, worst))
            flag = "OK" if worst <= TOLERANCE else "MISMATCH"
            print(f"  {label + ' [py]':<24}" + "".join(f"{v:>17,.0f}" for v in py))
            print(f"  {'  [excel]':<24}" + "".join(f"{v:>17,.0f}" for v in xl)
                  + f"   {worst * 100:.4f}%  {flag}")

        # balance check should be ~0 on both sides
        max_check = max(abs(v) for v in bs["balance_check"])
        print(f"\n  balance_check max |Liab-Assets|: {max_check:,.6f}  (tautology — always ~0)")

        # the REAL solvency signal
        neg = bs["negative_cash_flag"]
        if any(neg):
            any_negative_cash = True
            yrs = [i + 1 for i, f in enumerate(neg) if f]
            print(f"  negative_cash_flag: TRUE in year(s) {yrs}  -> "
                  + ", ".join(f"Y{y}={bs['cash_balancing_figure'][y-1]:,.0f}" for y in yrs))
            print("     (funding shortfall the tautological balance_check cannot detect)")
        else:
            print(f"  negative_cash_flag: all False (cash plug positive every year: "
                  + ", ".join(f"{c/1e6:.2f}M" for c in bs["cash_balancing_figure"]) + ")")
        wb.close()
        print()

    print("=" * 116)
    print(f"WORST DEVIATION ACROSS {len(files)} WORKBOOKS: {overall * 100:.8f}%")
    print(f"negative_cash_flag fired on any of the 3 test cases: {any_negative_cash}")
    if failures:
        print(f"FAILED — {len(failures)} line(s) outside {TOLERANCE * 100}%:")
        for wbname, label, py, xl, worst in failures:
            print(f"  {wbname} / {label}: {worst * 100:.3f}%")
            print(f"    python: {[round(v, 2) for v in py]}")
            print(f"    excel : {[round(v, 2) for v in xl]}")
        raise AssertionError(f"{len(failures)} line(s) differ from Excel by more than "
                             f"{TOLERANCE * 100}%")
    print(f"PASSED — every balance-sheet line matches Excel within {TOLERANCE * 100}%")
    print("across all 5 years of all 3 workbooks, including cumulative reserves and")
    print("accumulated depreciation (left-fold), and the balancing-cash plug.")
    print("=" * 116)
    return 0


if __name__ == "__main__":
    sys.exit(main())
