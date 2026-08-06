"""
test_full_engine_integration.py

End-to-end integration test for the generic financial engine.

Unlike the per-module tests — which each pull some intermediate values from the Excel
workbook as a convenient ground truth — this test starts from ONLY an assumptions
dict and chains EVERY module in sequence, exactly as a real caller (with no Excel)
would:

    assumptions
        -> revenue_calc        (production, revenue)
        -> expense_calc        (variable + fixed costs)
        -> depreciation_calc   (depreciation)
        -> loan_schedule_calc  (amortisation)
        -> working_capital_calc(WC build-up, MPBF, WC interest)
        -> profit_calc         (EBITDA -> PAT)
        -> balance_sheet_calc  (cumulative reserves, balancing cash)
        -> ratios_calc         (all ratios + DSCR)

The ONLY thing read from each workbook is its input assumptions (via the Assumptions
sheet) and the FINAL outputs used as ground truth. No intermediate Excel value feeds
the Python chain — if any module were wrong, or the modules failed to compose, the
final numbers would drift. Proving they don't proves the engine works as one piece.

Final outputs compared against Excel: PAT, the full balance sheet, DSCR (per-year +
average), and the key ratios.

Run from backend/:
    python financial_engine/calculations/generic/test_full_engine_integration.py
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
    read_assumptions, annual_row, annual_from_monthly,
)
from financial_engine.calculations.generic.test_profit_manual import profit_annual  # noqa: E402
from financial_engine.calculations.generic.revenue_calc import (  # noqa: E402
    calculate_monthly_production, calculate_monthly_revenue, yearly_totals,
)
from financial_engine.calculations.generic.expense_calc import (  # noqa: E402
    calculate_monthly_variable_costs, calculate_monthly_fixed_costs,
)
from financial_engine.calculations.generic.depreciation_calc import (  # noqa: E402
    calculate_monthly_depreciation, calculate_annual_depreciation,
)
from financial_engine.calculations.generic.loan_schedule_calc import (  # noqa: E402
    calculate_loan_schedule,
)
from financial_engine.calculations.generic.working_capital_calc import (  # noqa: E402
    calculate_working_capital,
)
from financial_engine.calculations.generic.profit_calc import (  # noqa: E402
    calculate_profit_and_loss,
)
from financial_engine.calculations.generic.balance_sheet_calc import (  # noqa: E402
    calculate_balance_sheet,
)
from financial_engine.calculations.generic.ratios_calc import calculate_ratios  # noqa: E402

TOLERANCE = 0.005  # 0.5%


def run_engine(assumptions: dict) -> dict:
    """The whole engine, from an assumptions dict to final outputs. NO Excel reads.
    This is exactly what a production caller would write."""
    a = assumptions

    # 1. Revenue
    production = calculate_monthly_production(a)
    revenue = calculate_monthly_revenue(a, production)

    # 2. Expenses
    var = calculate_monthly_variable_costs(a, production)
    fix = calculate_monthly_fixed_costs(a, revenue)

    # 3. Depreciation
    dep_monthly = calculate_monthly_depreciation(a)
    dep_annual = calculate_annual_depreciation(a)

    # 4. Loan schedule
    loan = calculate_loan_schedule(a)

    # 5. Working capital (needs annual revenue, cost of production, purchases)
    annual_revenue = yearly_totals(revenue)
    cop = [c1 + c2 + w + ov + fo + rmn + dep_annual for c1, c2, w, ov, fo, rmn in zip(
        yearly_totals(var["cost1"]), yearly_totals(var["cost2"]),
        yearly_totals(fix["wages"]), yearly_totals(var["other_variable"]),
        yearly_totals(fix["factory_overheads"]), yearly_totals(fix["repairs_maintenance"]))]
    wc = calculate_working_capital(
        a, annual_revenue=annual_revenue,
        annual_cost_of_production_ex_wc_interest=cop,
        wc_interest_rate=a["interest_rate_wc"], annual_purchases=yearly_totals(var["cost1"]))

    # 6. Profit & loss
    pl = calculate_profit_and_loss(
        a, monthly_revenue=revenue, monthly_variable_costs=var, monthly_fixed_costs=fix,
        monthly_depreciation=dep_monthly,
        loan_interest_annual=loan["interest"], wc_interest_annual=wc["wc_interest_annual"])

    # 7. Balance sheet
    bs = calculate_balance_sheet(
        a, annual_pat=pl["pat"], annual_depreciation_total=[dep_annual] * 5, wc_data=wc)

    # 8. Ratios + DSCR
    ratios = calculate_ratios(a, pl=pl, balance_sheet=bs, loan_schedule=loan, wc_data=wc)

    return {"pl": pl, "balance_sheet": bs, "ratios": ratios, "loan": loan, "wc": wc}


def _cmp(label, py, xl, failures, overall, wbname):
    pcts = [abs(p - e) / (abs(e) if abs(e) > 1e-9 else (abs(p) if abs(p) > 1e-9 else 1.0))
            for p, e in zip(py, xl)]
    worst = max(pcts) if pcts else 0.0
    if worst > TOLERANCE:
        failures.append((wbname, label, py, xl, worst))
    flag = "OK" if worst <= TOLERANCE else "MISMATCH"
    print(f"  {label:<26}{worst * 100:>10.4f}%   {flag}")
    return max(overall, worst)


def main():
    files = sorted(p for p in glob.glob(str(BACKEND_DIR / "generated_reports" / "*.xlsx"))
                   if not os.path.basename(p).startswith("~$"))
    if not files:
        print("[!] No workbooks in generated_reports/.")
        return 1

    failures, overall = [], 0.0
    for path in files:
        wb = load_workbook(path, data_only=True)
        a = read_assumptions(wb)          # ONLY the inputs are read from Excel
        out = run_engine(a)               # everything else is pure Python

        name = os.path.basename(path)
        print("=" * 72)
        print(f"{name}   —  engine run from assumptions only")
        print("=" * 72)
        print(f"  {'Final output':<26}{'max dev':>11}")
        print("  " + "-" * 44)

        # --- P&L: PAT (the figure DSCR consumes) ---
        overall = _cmp("PAT", out["pl"]["pat"],
                       annual_row(wb, "Annual_Summary", 26), failures, overall, name)
        overall = _cmp("EBITDA", out["pl"]["ebitda"],
                       profit_annual(wb, 14), failures, overall, name)

        # --- Balance sheet: the lines that depend on the whole chain ---
        overall = _cmp("Net worth", out["balance_sheet"]["net_worth"],
                       annual_row(wb, "Form_III_BalanceSheet", 8), failures, overall, name)
        overall = _cmp("Reserves (cumulative)", out["balance_sheet"]["reserves_surplus"],
                       annual_row(wb, "Form_III_BalanceSheet", 7), failures, overall, name)
        overall = _cmp("Total assets", out["balance_sheet"]["total_assets"],
                       annual_row(wb, "Form_III_BalanceSheet", 21), failures, overall, name)
        overall = _cmp("Cash (balancing)", out["balance_sheet"]["cash_balancing_figure"],
                       annual_row(wb, "Form_III_BalanceSheet", 20), failures, overall, name)

        # --- Ratios + DSCR ---
        overall = _cmp("DSCR", out["ratios"]["dscr"],
                       annual_row(wb, "DSCR", 14), failures, overall, name)
        overall = _cmp("Current ratio", out["ratios"]["current_ratio"],
                       annual_row(wb, "Ratios", 6), failures, overall, name)
        overall = _cmp("Debt-equity", out["ratios"]["debt_equity"],
                       annual_row(wb, "Ratios", 7), failures, overall, name)
        overall = _cmp("Net profit margin", out["ratios"]["net_profit_margin"],
                       annual_row(wb, "Ratios", 11), failures, overall, name)
        overall = _cmp("Break-even %", out["ratios"]["break_even_pct"],
                       annual_row(wb, "Ratios", 16), failures, overall, name)

        # average DSCR (single value)
        xl_avg = float(wb["DSCR"]["H14"].value)
        overall = _cmp("Average DSCR", [out["ratios"]["average_dscr"]], [xl_avg],
                       failures, overall, name)

        # the solvency signal the engine surfaces on its own
        neg = out["balance_sheet"]["negative_cash_flag"]
        print(f"  negative_cash_flag        : {neg}")
        wb.close()
        print()

    print("=" * 72)
    print(f"WORST DEVIATION, ENGINE vs EXCEL (final outputs): {overall * 100:.8f}%")
    if failures:
        print(f"FAILED — {len(failures)} output(s) drifted beyond {TOLERANCE * 100}%:")
        for wbname, label, py, xl, worst in failures:
            print(f"  {wbname} / {label}: {worst * 100:.3f}%")
            print(f"    python: {[round(v, 4) for v in py]}")
            print(f"    excel : {[round(v, 4) for v in xl]}")
        raise AssertionError(f"{len(failures)} final output(s) differ from Excel by more "
                             f"than {TOLERANCE * 100}%")
    print("PASSED — the full engine, driven from an assumptions dict alone, reproduces")
    print("Excel's PAT, balance sheet, DSCR and ratios within 0.5% for all 3 businesses.")
    print("The modules compose end-to-end as one engine, not just individually.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
