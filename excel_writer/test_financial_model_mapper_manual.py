"""
test_financial_model_mapper_manual.py

Standalone test: run the real engine -> build the canonical FinancialModel -> build
the workbook-independent Excel mapping. Verifies every worksheet payload exists, that
representative values are identical to the model (no mutation), and that malformed
input raises ValueError.

Run from backend/:
    python excel_writer/test_financial_model_mapper_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.engine.financial_engine_runner import run_financial_engine  # noqa: E402
from financial_engine.models.financial_model_builder import build_financial_model  # noqa: E402
from excel_writer.financial_model_mapper import build_excel_mapping  # noqa: E402

ASSUMPTIONS = {
    "name_of_unit": "Demo Manufacturing Pvt Ltd", "constitution": "Private Limited",
    "line_of_activity": "Precision components", "industry_type": "Manufacturing",
    "term_loan_amount": 4_000_000, "promoters_capital": 2_000_000,
    "interest_rate_term_loan": 0.11, "term_loan_tenure_months": 60,
    "moratorium_months": 0, "interest_rate_wc": 0.12, "income_tax_rate": 0.25,
    "installed_capacity": 300_000,
    "capacity_utilisation_y1_y5": [0.6, 0.7, 0.75, 0.8, 0.85],
    "monthly_seasonality_weights": [1] * 12,
    "selling_price_y1": 100, "selling_price_escalation": 0.05,
    "cost1_per_unit_y1": 40, "cost1_escalation": 0.05,
    "cost2_per_unit_y1": 15, "cost2_escalation": 0.05,
    "other_variable_cost_y1": 5, "other_variable_escalation": 0.05,
    "wages_monthly_y1": 150_000, "wages_escalation": 0.08,
    "factory_overheads_monthly_y1": 80_000, "factory_oh_escalation": 0.06,
    "repairs_maintenance_monthly_y1": 20_000, "rm_escalation": 0.06,
    "admin_expenses_monthly_y1": 40_000, "admin_escalation": 0.06,
    "selling_distribution": 0.02,
    "land_cost": 500_000, "building_cost": 2_000_000, "building_dep_rate": 0.10,
    "plant_machinery_cost": 4_000_000, "plant_machinery_dep_rate": 0.15,
    "furniture_other_cost": 500_000, "furniture_dep_rate": 0.15,
    "raw_material_holding_days": 30, "finished_goods_holding_days": 15,
    "receivables_days": 45, "payables_days": 30,
    "min_cash_balance": 100_000, "wc_margin_pct": 0.25,
    "discount_rate": 0.12,
}

WORKSHEETS = ["Dashboard", "ProfitLoss", "BalanceSheet", "CashFlow", "Ratios",
              "LoanSchedule", "WorkingCapital", "Depreciation"]

fails = []


def ok(cond, label):
    print(f"   {'OK ' if cond else 'FAIL'}  {label}")
    if not cond:
        fails.append(label)


def main():
    # 1-3. engine -> model -> mapping
    engine = run_financial_engine(ASSUMPTIONS)
    model = build_financial_model(engine)
    mapping = build_excel_mapping(model)

    print("=" * 74)
    print("EXCEL MODEL MAPPER")
    print("=" * 74)

    print("\n4. All worksheet payloads exist:")
    for w in WORKSHEETS:
        ok(w in mapping and mapping[w] is not None, w)

    print("\n5. Representative values identical to the FinancialModel:")
    checks = [
        ("Revenue (Dashboard vs wc.net_sales)",
         mapping["Dashboard"]["Revenue"],
         model["supporting_schedules"]["working_capital"]["net_sales"]),
        ("PAT (ProfitLoss vs financials.profit)",
         mapping["ProfitLoss"]["pat"], model["financials"]["profit"]["pat"]),
        ("PAT (Dashboard)", mapping["Dashboard"]["PAT"], model["financials"]["profit"]["pat"]),
        ("IRR (Dashboard vs financials.irr_npv)",
         mapping["Dashboard"]["IRR"], model["financials"]["irr_npv"]["irr"]),
        ("DSCR (Ratios vs financials.ratios)",
         mapping["Ratios"]["dscr"], model["financials"]["ratios"]["dscr"]),
        ("Assets (BalanceSheet vs financials.balance_sheet)",
         mapping["BalanceSheet"]["total_assets"],
         model["financials"]["balance_sheet"]["total_assets"]),
        ("Loan Principal (LoanSchedule vs supporting_schedules.loan_schedule)",
         mapping["LoanSchedule"]["principal"],
         model["supporting_schedules"]["loan_schedule"]["principal"]),
    ]
    for label, got, expected in checks:
        ok(got == expected, f"{label}: {str(got)[:40]}")

    print("\n   Dashboard snapshot:")
    d = mapping["Dashboard"]
    print(f"      Revenue = {['{:,.0f}'.format(x) for x in d['Revenue']]}")
    print(f"      PAT     = {['{:,.0f}'.format(x) for x in d['PAT']]}")
    print(f"      IRR     = {d['IRR']:.4f}   NPV = {d['NPV']:,.0f}")
    print(f"      DSCR    = {['{:.2f}'.format(x) for x in d['DSCR']]}")

    print("\n6. Malformed input raises ValueError:")
    for label, bad in [
        ("non-dict", "not a dict"),
        ("missing 'financials'", {k: v for k, v in model.items() if k != "financials"}),
        ("financials missing 'profit'",
         {**model, "financials": {k: v for k, v in model["financials"].items() if k != "profit"}}),
    ]:
        try:
            build_excel_mapping(bad)
            ok(False, f"{label} -> should have raised")
        except ValueError as e:
            ok(True, f"{label} -> ValueError: {str(e).split(':',1)[1].strip()[:34]}")

    print("\n" + "=" * 74)
    if fails:
        print(f"FAILED — {len(fails)} check(s): {fails}")
        raise AssertionError("financial_model_mapper did not behave as specified")
    print("PASSED — all 8 worksheet payloads built, values identical to the model,")
    print("malformed inputs rejected. No calculation, no Excel, no openpyxl.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
