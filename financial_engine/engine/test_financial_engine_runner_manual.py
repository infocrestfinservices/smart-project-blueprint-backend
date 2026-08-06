"""
test_financial_engine_runner_manual.py

Standalone integration test for the financial engine orchestrator. Runs the FULL
pipeline from one simple, complete assumptions dict and verifies that every section
of the returned dictionary exists and that the built-in validation passes.

The assumptions use a 5-year term loan with zero moratorium so the loan repays fully
within the projection window (total principal == loan), and capex slightly exceeds
loan+equity so the Year-0 net cash flow is negative — giving the IRR a genuine sign
change. All 44 base assumption fields are provided.

Run from backend/:
    python financial_engine/engine/test_financial_engine_runner_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.engine.financial_engine_runner import run_financial_engine  # noqa: E402

ASSUMPTIONS = {
    # text / identity (not used by the calculators, included for completeness)
    "name_of_unit": "Demo Manufacturing Pvt Ltd", "constitution": "Private Limited",
    "line_of_activity": "Precision components", "industry_type": "Manufacturing",
    # financing
    "term_loan_amount": 4_000_000, "promoters_capital": 2_000_000,
    "interest_rate_term_loan": 0.11, "term_loan_tenure_months": 60,
    "moratorium_months": 0, "interest_rate_wc": 0.12, "income_tax_rate": 0.25,
    # capacity & ramp
    "installed_capacity": 300_000,
    "capacity_utilisation_y1_y5": [0.6, 0.7, 0.75, 0.8, 0.85],
    "monthly_seasonality_weights": [1] * 12,
    # price & variable costs
    "selling_price_y1": 100, "selling_price_escalation": 0.05,
    "cost1_per_unit_y1": 40, "cost1_escalation": 0.05,
    "cost2_per_unit_y1": 15, "cost2_escalation": 0.05,
    "other_variable_cost_y1": 5, "other_variable_escalation": 0.05,
    # fixed / period costs
    "wages_monthly_y1": 150_000, "wages_escalation": 0.08,
    "factory_overheads_monthly_y1": 80_000, "factory_oh_escalation": 0.06,
    "repairs_maintenance_monthly_y1": 20_000, "rm_escalation": 0.06,
    "admin_expenses_monthly_y1": 40_000, "admin_escalation": 0.06,
    "selling_distribution": 0.02,
    # capex block
    "land_cost": 500_000, "building_cost": 2_000_000, "building_dep_rate": 0.10,
    "plant_machinery_cost": 4_000_000, "plant_machinery_dep_rate": 0.15,
    "furniture_other_cost": 500_000, "furniture_dep_rate": 0.15,
    # working-capital norms
    "raw_material_holding_days": 30, "finished_goods_holding_days": 15,
    "receivables_days": 45, "payables_days": 30,
    "min_cash_balance": 100_000, "wc_margin_pct": 0.25,
    # feasibility-style extra (optional; runner defaults 0.12 if absent)
    "discount_rate": 0.12,
}

REQUIRED_SECTIONS = ["assumptions", "profit", "depreciation", "working_capital",
                     "loan_schedule", "cash_flow", "irr_npv", "balance_sheet",
                     "ratios", "validation", "metadata"]


def main():
    result = run_financial_engine(ASSUMPTIONS)

    print("=" * 74)
    print("FINANCIAL ENGINE RUNNER — full pipeline from one assumptions dict")
    print("=" * 74)

    print("\n1. Every required section present:")
    missing = [s for s in REQUIRED_SECTIONS if s not in result]
    for s in REQUIRED_SECTIONS:
        ok = s in result and result[s] is not None
        print(f"   {'OK ' if ok else 'MISSING'}  {s}")
    assert not missing, f"missing sections: {missing}"

    print("\n2. Metadata:")
    md = result["metadata"]
    print(f"   engine_version = {md['engine_version']}   status = {md['status']}")
    assert md["engine_version"] == "1.0" and md["status"] == "success"

    print("\n3. Section contents are non-empty / correctly shaped:")
    checks = {
        "profit.pat (5 yrs)":            len(result["profit"]["pat"]) == 5,
        "depreciation.annual_series":    len(result["depreciation"]["annual_depreciation_series"]) == 5,
        "working_capital.mpbf":          len(result["working_capital"]["mpbf"]) == 5,
        "loan_schedule.principal":       len(result["loan_schedule"]["principal"]) == 5,
        "cash_flow.series (6 = yr0..5)":  len(result["cash_flow"]["cash_flow_series"]) == 6,
        "irr_npv has irr & npv":         ("irr" in result["irr_npv"] and "npv" in result["irr_npv"]),
        "balance_sheet.total_assets":    len(result["balance_sheet"]["total_assets"]) == 5,
        "ratios.dscr (5 yrs)":           len(result["ratios"]["dscr"]) == 5,
    }
    for label, ok in checks.items():
        print(f"   {'OK ' if ok else 'FAIL'}  {label}")
        assert ok, label

    print("\n4. Headline numbers (sanity):")
    r = result
    print(f"   Year-1 revenue    : {sum(r['profit'].get('monthly_ebitda', [0]))!s:>0}" if False else "", end="")
    print(f"   PAT (5 yrs)       : {['{:,.0f}'.format(x) for x in r['profit']['pat']]}")
    print(f"   DSCR (5 yrs)      : {['{:.2f}'.format(x) for x in r['ratios']['dscr']]}")
    print(f"   Avg DSCR          : {r['ratios']['average_dscr']:.3f}")
    print(f"   IRR               : {r['irr_npv']['irr']:.4f}" if r['irr_npv']['irr'] is not None else "   IRR: None")
    print(f"   NPV @ {ASSUMPTIONS['discount_rate']:.0%}         : {r['irr_npv']['npv']:,.0f}")
    print(f"   Cash flow series  : {['{:,.0f}'.format(x) for x in r['cash_flow']['cash_flow_series']]}")

    print("\n5. Built-in validation:")
    v = result["validation"]
    print(f"   passed = {v['passed']}   errors = {len(v['errors'])}   warnings = {len(v['warnings'])}")
    for e in v["errors"]:
        print(f"      ERROR: {e}")
    for w in v["warnings"]:
        print(f"      warn : {w}")

    print("\n" + "=" * 74)
    assert v["passed"], f"validation did not pass: {v['errors']}"
    print("PASSED — full pipeline executed, every section present, validation passed.")
    print("=" * 74)

    # bonus: malformed input still raises ValueError from the orchestrator
    try:
        run_financial_engine("not a dict")
        print("BONUS FAIL: non-dict assumptions did not raise")
        return 1
    except ValueError as e:
        print(f"bonus: non-dict assumptions -> ValueError ({str(e)[:50]}...)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
