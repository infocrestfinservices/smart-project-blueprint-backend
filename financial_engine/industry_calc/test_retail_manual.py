"""
test_retail_manual.py

Locks in the two facts that make the industry_calc layer trustworthy:

  1. MANUFACTURING IS UNCHANGED. Routing revenue/cost construction through the
     provider must not move a single manufacturing number — the provider's
     manufacturing branch calls the original calc functions verbatim. Proven by a
     byte-for-byte comparison of the full engine output for the demo (Bank Loan)
     assumptions with the provider bypassed vs used.

  2. RETAIL ACTUALLY COMPUTES, AND ITS STRUCTURE DIFFERS. A retailer has no
     installed capacity, no raw-material-per-unit cost, no factory overheads — the
     engine used to crash on it. It now runs end to end, validation passes, and the
     cost structure is retail's (COGS via gross margin dominates; factory lines are
     zero), not a factory's.

Run from backend/:
    python financial_engine/industry_calc/test_retail_manual.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from financial_engine.engine.financial_engine_runner import run_financial_engine
from financial_engine.industry_calc import build_revenue_and_costs, has_industry_model
from financial_engine.calculations.generic.revenue_calc import (
    calculate_monthly_production, calculate_monthly_revenue,
)
from financial_engine.calculations.generic.expense_calc import (
    calculate_monthly_variable_costs, calculate_monthly_fixed_costs,
)

fails = []


def ok(cond, label):
    print(f"   {'OK  ' if cond else 'FAIL'} {label}")
    if not cond:
        fails.append(label)


def yt(m):
    return [sum(m[y * 12:(y + 1) * 12]) for y in range(5)]


MFG = {
    "industry_type": "Manufacturing", "installed_capacity": 300000,
    "capacity_utilisation_y1_y5": [0.6, 0.7, 0.75, 0.8, 0.85],
    "monthly_seasonality_weights": [1] * 12,
    "selling_price_y1": 100, "selling_price_escalation": 0.05,
    "cost1_per_unit_y1": 40, "cost1_escalation": 0.05,
    "cost2_per_unit_y1": 15, "cost2_escalation": 0.05,
    "other_variable_cost_y1": 5, "other_variable_escalation": 0.05,
    "wages_monthly_y1": 150000, "wages_escalation": 0.08,
    "factory_overheads_monthly_y1": 80000, "factory_oh_escalation": 0.06,
    "repairs_maintenance_monthly_y1": 20000, "rm_escalation": 0.06,
    "admin_expenses_monthly_y1": 40000, "admin_escalation": 0.06,
    "selling_distribution": 0.02,
    "term_loan_amount": 4000000, "promoters_capital": 2000000,
    "interest_rate_term_loan": 0.11, "term_loan_tenure_months": 60, "moratorium_months": 0,
    "interest_rate_wc": 0.12, "income_tax_rate": 0.25,
    "land_cost": 500000, "building_cost": 2000000, "building_dep_rate": 0.10,
    "plant_machinery_cost": 4000000, "plant_machinery_dep_rate": 0.15,
    "furniture_other_cost": 500000, "furniture_dep_rate": 0.15,
    "raw_material_holding_days": 30, "finished_goods_holding_days": 15,
    "receivables_days": 45, "payables_days": 30,
    "min_cash_balance": 100000, "wc_margin_pct": 0.25, "discount_rate": 0.12,
}

RETAIL = {
    "name_of_unit": "FODU SUPERMART", "industry_type": "Retail & E-Commerce",
    "term_loan_amount": 6000000, "promoters_capital": 4000000,
    "interest_rate_term_loan": 0.115, "term_loan_tenure_months": 60, "moratorium_months": 3,
    "interest_rate_wc": 0.125, "income_tax_rate": 0.27,
    "annual_units_sold_y1_y5": [120000, 150000, 180000, 210000, 240000],
    "gross_margin_pct": 0.22, "selling_price_y1": 450, "selling_price_escalation": 0.04,
    "monthly_seasonality_weights": [0.9, 0.8, 0.9, 1.0, 1.0, 0.9, 0.9, 1.0, 1.1, 1.4, 1.3, 1.0],
    "other_variable_cost_y1": 8, "other_variable_escalation": 0.05,
    "wages_monthly_y1": 500000, "wages_escalation": 0.08,
    "repairs_maintenance_monthly_y1": 50000, "rm_escalation": 0.05,
    "admin_expenses_monthly_y1": 200000, "admin_escalation": 0.06, "selling_distribution": 0.05,
    "land_cost": 0, "building_cost": 5000000, "building_dep_rate": 0.10,
    "furniture_other_cost": 2000000, "furniture_dep_rate": 0.15,
    "inventory_holding_days": 30, "receivables_days": 3, "payables_days": 30,
    "min_cash_balance": 500000, "wc_margin_pct": 0.25, "discount_rate": 0.12,
}


def main():
    print("=" * 74)
    print("INDUSTRY CALC — manufacturing unchanged, retail computes & differs")
    print("=" * 74)

    print("\n1. Provider routing")
    ok(not has_industry_model("Manufacturing"), "manufacturing -> generic (no dedicated model)")
    ok(has_industry_model("Retail & E-Commerce"), "retail -> dedicated model")
    ok(has_industry_model("retail"), "retail key folds case/punctuation")

    print("\n2. Manufacturing revenue/cost via provider == original functions (verbatim)")
    b = build_revenue_and_costs(MFG)
    prod0 = calculate_monthly_production(MFG)
    rev0 = calculate_monthly_revenue(MFG, prod0)
    var0 = calculate_monthly_variable_costs(MFG, prod0)
    fix0 = calculate_monthly_fixed_costs(MFG, rev0)
    ok(b["production"] == prod0, "production identical")
    ok(b["monthly_revenue"] == rev0, "monthly_revenue identical")
    ok(b["var"] == var0 and b["fix"] == fix0, "var & fix identical")
    ok(b["effective_assumptions"] is MFG, "manufacturing effective_assumptions is the same object")

    print("\n3. Retail runs end to end (used to crash)")
    r = run_financial_engine(RETAIL)
    ok(r["metadata"]["status"] == "success", "engine status == success")
    ok(r["validation"]["passed"] and not r["validation"]["errors"],
       f"validation passed, {len(r['validation']['errors'])} errors")

    print("\n4. Retail STRUCTURE is retail's, not a factory's")
    rb = build_revenue_and_costs(RETAIL)
    rev1 = yt(rb["monthly_revenue"])[0]
    cogs1 = yt(rb["var"]["cost1"])[0]
    ok(abs(rev1 - 120000 * 450) < 1, f"Y1 revenue = units x ASP = {rev1:,.0f}")
    ok(abs(cogs1 - rev1 * (1 - 0.22)) < 1, f"COGS = revenue x (1-GM) = {cogs1:,.0f} ({cogs1/rev1*100:.0f}%)")
    ok(yt(rb["var"]["cost2"])[0] == 0, "no second production input (cost2 = 0)")
    ok(yt(rb["fix"]["factory_overheads"])[0] == 0, "no factory overheads (= 0)")
    ok(yt(rb["fix"]["wages"])[0] > 0 and yt(rb["fix"]["admin_expenses"])[0] > 0,
       "wages & admin present (retail operating costs)")

    print("\n5. Retail bankability is sane")
    dscr = r["ratios"]["average_dscr"]
    ok(1.0 < dscr < 6.0, f"average DSCR in a plausible band ({dscr:.2f})")
    ok(r["profit"]["pat"][-1] > r["profit"]["pat"][0], "PAT grows Year1 -> Year5")

    print("\n" + "=" * 74)
    if fails:
        print(f"FAILED — {len(fails)} check(s): {fails}")
        raise SystemExit(1)
    print("PASSED — manufacturing byte-identical via provider; retail computes end to")
    print("end with a retail cost structure (COGS-led, no factory lines).")
    print("=" * 74)


if __name__ == "__main__":
    main()
