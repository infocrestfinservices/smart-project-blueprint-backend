"""
financial_model_mapper.py

Converts the canonical FinancialModel (from build_financial_model) into a
WORKBOOK-INDEPENDENT mapping of values — one logical payload per worksheet.

This is a pure reorganizer. It:
  * validates the canonical structure is present, and
  * groups the model's data into named worksheet payloads.

It does NOT calculate, does NOT format numbers, does NOT reference Excel cells, does
NOT open workbooks, and imports NEITHER openpyxl NOR anything LibreOffice-related. The
actual cell placement / styling is the job of a downstream Excel writer; this module
only decides WHAT goes on each sheet, not WHERE.

Every value is passed through by reference exactly as the FinancialModel holds it, so
the numbers are identical to the model's.

Note on Revenue: the profit section carries no `revenue` line, but the annual revenue
already exists losslessly in the model as working_capital["net_sales"] (the value the
engine fed in). The Dashboard reads it from there — a relabel, not a calculation.

Raises ValueError only for malformed input.
"""

from __future__ import annotations

_REQUIRED_TOP = ("metadata", "assumptions", "financials", "supporting_schedules", "validation")
_REQUIRED_FINANCIALS = ("profit", "balance_sheet", "cash_flow", "ratios", "irr_npv")
_REQUIRED_SCHEDULES = ("depreciation", "working_capital", "loan_schedule")


def build_excel_mapping(financial_model: dict) -> dict:
    """Reorganize a canonical FinancialModel into per-worksheet payloads.

    Returns {Dashboard, ProfitLoss, BalanceSheet, CashFlow, Ratios, LoanSchedule,
    WorkingCapital, Depreciation}. Raises ValueError for a non-dict or a model missing
    a required (sub)section.
    """
    fn = "build_excel_mapping"
    if not isinstance(financial_model, dict):
        raise ValueError(f"{fn}: financial_model must be a dict, "
                         f"got {type(financial_model).__name__}")

    missing = [s for s in _REQUIRED_TOP
               if s not in financial_model or financial_model[s] is None]
    if missing:
        raise ValueError(f"{fn}: financial_model is missing required section(s): "
                         f"{', '.join(missing)}")

    financials = financial_model["financials"]
    schedules = financial_model["supporting_schedules"]
    if not isinstance(financials, dict):
        raise ValueError(f"{fn}: 'financials' must be a dict, got {type(financials).__name__}")
    if not isinstance(schedules, dict):
        raise ValueError(f"{fn}: 'supporting_schedules' must be a dict, "
                         f"got {type(schedules).__name__}")

    miss_fin = [s for s in _REQUIRED_FINANCIALS if s not in financials]
    if miss_fin:
        raise ValueError(f"{fn}: 'financials' is missing: {', '.join(miss_fin)}")
    miss_sch = [s for s in _REQUIRED_SCHEDULES if s not in schedules]
    if miss_sch:
        raise ValueError(f"{fn}: 'supporting_schedules' is missing: {', '.join(miss_sch)}")

    profit = financials["profit"]
    balance_sheet = financials["balance_sheet"]
    cash_flow = financials["cash_flow"]
    ratios = financials["ratios"]
    irr_npv = financials["irr_npv"]
    depreciation = schedules["depreciation"]
    working_capital = schedules["working_capital"]
    loan_schedule = schedules["loan_schedule"]

    return {
        # Curated headline KPIs — every value pulled by reference from the sections.
        "Dashboard": {
            "Revenue": working_capital.get("net_sales"),
            "PAT": profit.get("pat"),
            "EBITDA": profit.get("ebitda"),
            "IRR": irr_npv.get("irr"),
            "NPV": irr_npv.get("npv"),
            "DSCR": ratios.get("dscr"),
        },
        # Each remaining worksheet receives its whole section, unchanged.
        "ProfitLoss": profit,
        "BalanceSheet": balance_sheet,
        "CashFlow": cash_flow,
        "Ratios": ratios,
        "LoanSchedule": loan_schedule,
        "WorkingCapital": working_capital,
        "Depreciation": depreciation,
    }
