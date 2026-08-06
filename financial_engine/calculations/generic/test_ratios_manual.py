"""
test_ratios_manual.py

Parity check for the financial ratios (and DSCR) against the real post-fix workbooks
in generated_reports/, recalculated by LibreOffice.

Ground truth = Ratios rows 6-16, columns C..G; plus DSCR!C14:G14 and DSCR!H14.

Run from backend/:
    python financial_engine/calculations/generic/test_ratios_manual.py
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
from financial_engine.calculations.generic.test_balance_sheet_manual import (  # noqa: E402
    build_balance_sheet,
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
from financial_engine.calculations.generic.loan_schedule_calc import (  # noqa: E402
    calculate_loan_schedule,
)
from financial_engine.calculations.generic.working_capital_calc import (  # noqa: E402
    calculate_working_capital,
)
from financial_engine.calculations.generic.ratios_calc import calculate_ratios  # noqa: E402

TOLERANCE = 0.005  # 0.5%

# Ratios row -> the key returned by calculate_ratios
RATIO_ROWS = [
    ("Current Ratio", 6, "current_ratio"),
    ("Debt-Equity", 7, "debt_equity"),
    ("TOL / TNW", 8, "tol_tnw"),
    ("EBITDA Margin", 10, "ebitda_margin"),
    ("Net Profit Margin", 11, "net_profit_margin"),
    ("Return on Cap. Employed", 12, "return_on_capital_employed"),
    ("Interest Coverage", 14, "interest_coverage"),
    ("DSCR", 15, "dscr"),
    ("Break-even (% sales)", 16, "break_even_pct"),
]


def build_ratios(wb, a):
    """Chain every calculator to produce the ratios for this workbook."""
    production = calculate_monthly_production(a)
    revenue = calculate_monthly_revenue(a, production)
    var = calculate_monthly_variable_costs(a, production)
    fix = calculate_monthly_fixed_costs(a, revenue)
    dep_a = calculate_annual_depreciation(a)

    loan = calculate_loan_schedule(a)
    cop = [c1 + c2 + w + ov + fo + rmn + dep_a for c1, c2, w, ov, fo, rmn in zip(
        yearly_totals(var["cost1"]), yearly_totals(var["cost2"]),
        yearly_totals(fix["wages"]), yearly_totals(var["other_variable"]),
        yearly_totals(fix["factory_overheads"]), yearly_totals(fix["repairs_maintenance"]))]
    wc = calculate_working_capital(
        a, annual_revenue=yearly_totals(revenue),
        annual_cost_of_production_ex_wc_interest=cop,
        wc_interest_rate=a["interest_rate_wc"], annual_purchases=yearly_totals(var["cost1"]))

    pl = build_pl(wb, a)
    bs = build_balance_sheet(wb, a)
    return calculate_ratios(a, pl=pl, balance_sheet=bs, loan_schedule=loan, wc_data=wc)


def main():
    files = sorted(p for p in glob.glob(str(BACKEND_DIR / "generated_reports" / "*.xlsx"))
                   if not os.path.basename(p).startswith("~$"))
    if not files:
        print("[!] No workbooks in generated_reports/.")
        return 1

    failures, overall = [], 0.0
    for path in files:
        wb = load_workbook(path, data_only=True)
        a = read_assumptions(wb)
        r = build_ratios(wb, a)

        print("=" * 104)
        print(os.path.basename(path))
        print("=" * 104)
        print(f"  {'Ratio':<26}{'Yr1':>13}{'Yr2':>13}{'Yr3':>13}{'Yr4':>13}{'Yr5':>13}   max%")
        print("  " + "-" * 98)
        for label, row, key in RATIO_ROWS:
            py = r[key]
            xl = annual_row(wb, "Ratios", row)
            pcts = [abs(p - e) / (abs(e) if abs(e) > 1e-9 else (abs(p) if abs(p) > 1e-9 else 1.0))
                    for p, e in zip(py, xl)]
            worst = max(pcts)
            overall = max(overall, worst)
            if worst > TOLERANCE:
                failures.append((os.path.basename(path), label, py, xl, worst))
            flag = "OK" if worst <= TOLERANCE else "MISMATCH"
            print(f"  {label + ' [py]':<26}" + "".join(f"{v:>13,.4f}" for v in py))
            print(f"  {'  [excel]':<26}" + "".join(f"{v:>13,.4f}" for v in xl)
                  + f"   {worst * 100:.4f}%  {flag}")

        # Average DSCR vs DSCR!H14
        xl_avg = wb["DSCR"]["H14"].value
        d = abs(r["average_dscr"] - float(xl_avg)) / (abs(float(xl_avg)) if xl_avg else 1.0)
        overall = max(overall, d)
        if d > TOLERANCE:
            failures.append((os.path.basename(path), "Average DSCR",
                             [r["average_dscr"]], [float(xl_avg)], d))
        print(f"\n  Average DSCR: py={r['average_dscr']:.4f}  excel(H14)={float(xl_avg):.4f}"
              f"   {d * 100:.4f}%  {'OK' if d <= TOLERANCE else 'MISMATCH'}")
        wb.close()
        print()

    print("=" * 104)
    print(f"WORST DEVIATION ACROSS {len(files)} WORKBOOKS: {overall * 100:.8f}%")
    if failures:
        print(f"FAILED — {len(failures)} line(s) outside {TOLERANCE * 100}%:")
        for wbname, label, py, xl, worst in failures:
            print(f"  {wbname} / {label}: {worst * 100:.3f}%")
            print(f"    python: {[round(v, 4) for v in py]}")
            print(f"    excel : {[round(v, 4) for v in xl]}")
        raise AssertionError(f"{len(failures)} line(s) differ from Excel by more than "
                             f"{TOLERANCE * 100}%")
    print(f"PASSED — every ratio (incl. DSCR per-year and average) matches Excel within")
    print(f"{TOLERANCE * 100}% across all 5 years of all 3 workbooks.")
    print("=" * 104)
    return 0


if __name__ == "__main__":
    sys.exit(main())
