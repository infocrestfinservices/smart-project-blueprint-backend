"""
test_financial_model_builder_manual.py

Standalone test for financial_model_builder: runs the real engine, reshapes the
output, and verifies the canonical structure, that validation passes, that metadata
is preserved, and that representative numbers are IDENTICAL before and after building
(no mutation). Also checks malformed inputs raise ValueError.

Run from backend/:
    python financial_engine/models/test_financial_model_builder_manual.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from financial_engine.engine.financial_engine_runner import run_financial_engine  # noqa: E402
from financial_engine.models.financial_model_builder import build_financial_model  # noqa: E402

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

fails = []


def ok(cond, label):
    print(f"   {'OK ' if cond else 'FAIL'}  {label}")
    if not cond:
        fails.append(label)


def main():
    # 1. run the real engine
    engine = run_financial_engine(ASSUMPTIONS)
    # 2. build the canonical model
    model = build_financial_model(engine)

    print("=" * 74)
    print("FINANCIAL MODEL BUILDER")
    print("=" * 74)

    print("\n3. Canonical structure — top-level sections:")
    for s in ("metadata", "assumptions", "financials", "supporting_schedules", "validation"):
        ok(s in model and model[s] is not None, s)
    print("   financials:")
    for s in ("profit", "balance_sheet", "cash_flow", "ratios", "irr_npv"):
        ok(s in model["financials"], f"financials.{s}")
    print("   supporting_schedules:")
    for s in ("depreciation", "working_capital", "loan_schedule"):
        ok(s in model["supporting_schedules"], f"supporting_schedules.{s}")

    print("\n4. validation.passed is True:")
    ok(model["validation"]["passed"] is True, f"validation.passed "
       f"(errors={len(model['validation']['errors'])})")

    print("\n5. metadata preserved:")
    ok(model["metadata"] == engine["metadata"], "metadata equals engine metadata")
    ok(model["metadata"]["engine_version"] == "1.0"
       and model["metadata"]["status"] == "success", "engine_version=1.0, status=success")

    print("\n6. representative numbers IDENTICAL before vs after building (no mutation):")
    pairs = [
        ("PAT", engine["profit"]["pat"], model["financials"]["profit"]["pat"]),
        ("total_assets", engine["balance_sheet"]["total_assets"],
         model["financials"]["balance_sheet"]["total_assets"]),
        ("IRR", engine["irr_npv"]["irr"], model["financials"]["irr_npv"]["irr"]),
        ("DSCR", engine["ratios"]["dscr"], model["financials"]["ratios"]["dscr"]),
        ("cash_flow_series", engine["cash_flow"]["cash_flow_series"],
         model["financials"]["cash_flow"]["cash_flow_series"]),
        ("depreciation.annual_series", engine["depreciation"]["annual_depreciation_series"],
         model["supporting_schedules"]["depreciation"]["annual_depreciation_series"]),
        ("loan principal", engine["loan_schedule"]["principal"],
         model["supporting_schedules"]["loan_schedule"]["principal"]),
    ]
    for label, before, after in pairs:
        same = before == after
        ok(same, f"{label}: {str(after)[:46]}")

    print("\n7. malformed inputs raise ValueError:")
    for label, bad in [("non-dict", "not a dict"),
                       ("missing 'ratios'", {k: v for k, v in engine.items() if k != "ratios"}),
                       ("section is None", {**engine, "profit": None})]:
        try:
            build_financial_model(bad)
            ok(False, f"{label} -> should have raised")
        except ValueError as e:
            ok(True, f"{label} -> ValueError: {str(e).split(':',1)[1].strip()[:36]}")

    print("\n" + "=" * 74)
    if fails:
        print(f"FAILED — {len(fails)} check(s): {fails}")
        raise AssertionError("financial_model_builder did not behave as specified")
    print("PASSED — canonical model built, structure correct, validation passed,")
    print("metadata preserved, numbers unchanged, malformed inputs rejected.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
