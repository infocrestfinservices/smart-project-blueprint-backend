"""
financial_engine_runner.py

Orchestrator for the generic financial engine. It performs NO financial calculations
of its own — it only calls the existing calculation modules in the correct dependency
order, threads each module's output into the next, and aggregates everything into one
result dictionary. No Excel, Word, API, or UI logic.

EXECUTION ORDER (real data-dependency order)
--------------------------------------------
The spec lists a conceptual order with Profit & Loss at #3, but profit_calc CONSUMES
depreciation, term-loan interest, and working-capital interest — so Depreciation,
Loan Schedule, and Working Capital must run BEFORE Profit & Loss or profit_calc would
have nothing to consume. The executable order is therefore:

    1. Revenue          (revenue_calc)
    2. Expenses         (expense_calc)
    3. Depreciation     (depreciation_calc)   ── moved ahead of P&L (P&L needs it)
    4. Loan Schedule    (loan_schedule_calc)  ── moved ahead of P&L (P&L needs interest)
    5. Working Capital  (working_capital_calc)── moved ahead of P&L (P&L needs WC interest)
    6. Profit & Loss    (profit_calc)
    7. Cash Flow        (cash_flow_builder)
    8. IRR / NPV        (irr_npv_calc)
    9. Balance Sheet    (balance_sheet_calc)
   10. Financial Ratios (ratios_calc)
   11. Validator        (financial_model_validator)

ADAPTERS FOR THE VALIDATOR
--------------------------
The validator has its own field contract that a couple of raw module outputs don't
literally match. The orchestrator ASSEMBLES the validator's inputs from existing
outputs (simple sums/renames — never a business recalculation):
  * profit needs `revenue` and `expenses`: revenue = the revenue module's annual
    totals; expenses = the sum of the eight operating-cost lines the expense module
    produced (exactly what EBITDA is net of).
  * balance sheet needs `total_liabilities` EXCLUDING equity and a separate
    `total_equity`: the CMA-style module reports total_liabilities INCLUDING net worth,
    so we pass the four external-liability lines it also returns, plus net_worth as
    equity.

If any module raises, execution stops and the failing module's name is included in a
ValueError.
"""

from __future__ import annotations

from financial_engine.calculations.generic.revenue_calc import yearly_totals
from financial_engine.industry_calc import build_revenue_and_costs
from financial_engine.calculations.generic.depreciation_calc import (
    calculate_monthly_depreciation, calculate_annual_depreciation, annual_depreciation_series,
)
from financial_engine.calculations.generic.loan_schedule_calc import calculate_loan_schedule
from financial_engine.calculations.generic.working_capital_calc import calculate_working_capital
from financial_engine.calculations.generic.profit_calc import calculate_profit_and_loss
from financial_engine.calculations.generic.cash_flow_builder import build_cash_flow_series
from financial_engine.calculations.generic.irr_npv_calc import calculate_irr_npv_payback
from financial_engine.calculations.generic.balance_sheet_calc import calculate_balance_sheet
from financial_engine.calculations.generic.ratios_calc import calculate_ratios
from financial_engine.calculations.generic.financial_model_validator import validate_financial_model

ENGINE_VERSION = "1.0"
_CAPEX_COMPONENTS = ("land_cost", "building_cost", "plant_machinery_cost", "furniture_other_cost")
_DEFAULT_DISCOUNT_RATE = 0.12
_DEFAULT_PROJECT_LIFE = 5


def _resolve_capex(assumptions: dict) -> float:
    """Year-0 capital expenditure — explicit 'capital_expenditure' or the sum of the
    four project-cost components. Raises ValueError (invalid assumptions) if neither."""
    explicit = assumptions.get("capital_expenditure")
    if explicit is not None:
        return float(explicit)
    if all(assumptions.get(k) is not None for k in _CAPEX_COMPONENTS):
        return sum(float(assumptions[k]) for k in _CAPEX_COMPONENTS)
    raise ValueError("run_financial_engine: assumptions must provide 'capital_expenditure' "
                     f"or all four cost components: {', '.join(_CAPEX_COMPONENTS)}.")


def run_financial_engine(assumptions: dict) -> dict:
    """Run the full financial engine from an assumptions dict and aggregate every
    section into one result dict (see module docstring for the structure)."""
    if not isinstance(assumptions, dict):
        raise ValueError(f"run_financial_engine: assumptions must be a dict, "
                         f"got {type(assumptions).__name__}")

    def step(module_name: str, fn):
        """Run one module step; on any failure raise ValueError naming the module."""
        try:
            return fn()
        except ValueError:
            raise  # module's own validation message is already clear; keep its type
        except Exception as e:
            raise ValueError(f"run_financial_engine: module '{module_name}' raised "
                             f"{type(e).__name__}: {e}") from e

    raw_assumptions = assumptions

    # 1-2. Revenue / Sales and Expenses, built by the industry's own model. For
    # manufacturing (and any industry without a dedicated model) this calls the
    # original revenue_calc / expense_calc verbatim, so the numbers are unchanged;
    # retail builds units x ASP revenue and COGS-via-gross-margin costs instead. The
    # returned `effective_assumptions` maps the industry's concepts onto the engine's
    # slots (identical object for manufacturing), and the whole tail computes on it.
    built = step("revenue_cost_provider", lambda: build_revenue_and_costs(assumptions))
    production = built["production"]
    monthly_revenue = built["monthly_revenue"]
    var = built["var"]
    fix = built["fix"]
    assumptions = built["effective_assumptions"]
    annual_revenue = yearly_totals(monthly_revenue)

    # 3. Depreciation (P&L consumes it -> computed before P&L)
    dep_monthly = step("depreciation_calc", lambda: calculate_monthly_depreciation(assumptions))
    dep_annual = step("depreciation_calc", lambda: calculate_annual_depreciation(assumptions))
    dep_series = step("depreciation_calc", lambda: annual_depreciation_series(assumptions))

    # 4. Loan schedule (P&L consumes its interest -> computed before P&L)
    loan = step("loan_schedule_calc", lambda: calculate_loan_schedule(assumptions))

    # 5. Working capital (P&L consumes its WC interest -> computed before P&L)
    cost1_a = yearly_totals(var["cost1"])
    cost2_a = yearly_totals(var["cost2"])
    other_a = yearly_totals(var["other_variable"])
    wages_a = yearly_totals(fix["wages"])
    foh_a = yearly_totals(fix["factory_overheads"])
    rep_a = yearly_totals(fix["repairs_maintenance"])
    cop = [cost1_a[t] + cost2_a[t] + wages_a[t] + other_a[t] + foh_a[t] + rep_a[t] + dep_annual
           for t in range(len(annual_revenue))]
    wc = step("working_capital_calc", lambda: calculate_working_capital(
        assumptions, annual_revenue=annual_revenue,
        annual_cost_of_production_ex_wc_interest=cop,
        wc_interest_rate=assumptions.get("interest_rate_wc"),
        annual_purchases=cost1_a))

    # 6. Profit & Loss
    profit = step("profit_calc", lambda: calculate_profit_and_loss(
        assumptions, monthly_revenue, var, fix, dep_monthly,
        loan["interest"], wc["wc_interest_annual"]))

    # 7. Cash Flow
    cash_flow = step("cash_flow_builder", lambda: build_cash_flow_series(
        assumptions, profit, {"annual_depreciation": dep_series}, wc, loan))

    # 8. IRR / NPV
    capex = _resolve_capex(assumptions)
    discount_rate = float(assumptions.get("discount_rate") or _DEFAULT_DISCOUNT_RATE)
    project_life = int(assumptions.get("project_life_years") or _DEFAULT_PROJECT_LIFE)
    irr_npv = step("irr_npv_calc", lambda: calculate_irr_npv_payback(
        assumptions, cash_flow["cash_flow_series"], capex, discount_rate, project_life))

    # 9. Balance Sheet
    bs = step("balance_sheet_calc", lambda: calculate_balance_sheet(
        assumptions, profit["pat"], dep_series, wc))

    # 10. Financial Ratios
    ratios = step("ratios_calc", lambda: calculate_ratios(
        assumptions, profit, bs, loan, wc, cost_lines={"var": var, "fix": fix}))

    # 11. Validator — assemble its contract from existing outputs (no recalculation)
    admin_a = yearly_totals(fix["admin_expenses"])
    sd_a = yearly_totals(fix["selling_distribution"])
    operating_expenses = [cost1_a[t] + cost2_a[t] + other_a[t] + wages_a[t] + foh_a[t]
                          + rep_a[t] + admin_a[t] + sd_a[t] for t in range(len(annual_revenue))]
    validator_profit = {
        "revenue": annual_revenue, "expenses": operating_expenses,
        "ebitda": profit["ebitda"], "ebit": profit["ebit"], "pbt": profit["pbt"],
        "tax": profit["income_tax"], "pat": profit["pat"],
    }
    external_liab = [bs["term_loan_closing"][t] + bs["wc_borrowing"][t]
                     + bs["sundry_creditors"][t] + bs["other_current_liabilities"][t]
                     for t in range(len(annual_revenue))]
    validator_bs = {"total_assets": bs["total_assets"], "total_liabilities": external_liab,
                    "total_equity": bs["net_worth"]}
    # The validator's current-ratio check (R13) compares ratios.current_ratio against
    # CA/CL. ratios_calc defines the current ratio on the BALANCE SHEET basis
    # (inventory + debtors + cash) / (creditors + other CL + WC borrowing) — NOT the
    # working-capital module's Form-IV totals (which serve MPBF). Feed the validator
    # the balance-sheet-basis CA/CL so R13 (and R10) validate the ratio against its own
    # components; wc_interest still comes from the real WC module for R3/R12.
    bs_ca = [bs["inventory"][t] + bs["debtors"][t] + bs["cash_balancing_figure"][t]
             for t in range(len(annual_revenue))]
    bs_cl = [bs["sundry_creditors"][t] + bs["other_current_liabilities"][t] + bs["wc_borrowing"][t]
             for t in range(len(annual_revenue))]
    validator_wc = {
        "current_assets": bs_ca, "current_liabilities": bs_cl,
        "working_capital": [bs_ca[t] - bs_cl[t] for t in range(len(annual_revenue))],
        "wc_interest_annual": wc["wc_interest_annual"],
    }
    validation = step("financial_model_validator", lambda: validate_financial_model(
        assumptions, validator_profit, {"annual_depreciation": dep_series}, validator_wc, loan,
        cash_flow, validator_bs, ratios,
        {"irr": irr_npv["irr"], "npv": irr_npv["npv"]}))

    return {
        "assumptions": raw_assumptions,
        "profit": profit,
        "depreciation": {
            "monthly_depreciation": dep_monthly,
            "annual_depreciation": dep_annual,
            "annual_depreciation_series": dep_series,
        },
        "working_capital": wc,
        "loan_schedule": loan,
        "cash_flow": cash_flow,
        "irr_npv": irr_npv,
        "balance_sheet": bs,
        "ratios": ratios,
        "validation": validation,
        "metadata": {"engine_version": ENGINE_VERSION, "status": "success"},
    }
