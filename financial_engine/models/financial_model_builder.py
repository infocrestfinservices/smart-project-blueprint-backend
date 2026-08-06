"""
financial_model_builder.py

Turns the raw output of run_financial_engine() into a standardized FinancialModel
structure — the canonical shape that Excel writers, Word report generators, APIs,
dashboards, and future integrations all consume.

This builder is a PURE RESHAPER. It:
  * validates that every required section is present, and
  * reorganizes the sections into a stable schema (headline financial statements
    under "financials", the supporting schedules under "supporting_schedules").

It performs NO financial calculation, derives NO new metric, and modifies NO numeric
value. Each section is passed through by reference exactly as the engine produced it,
so numbers before and after building are identical.

Raises ValueError only for malformed input: a non-dict, or a missing required section.
"""

from __future__ import annotations

# The sections run_financial_engine() must have produced.
_REQUIRED_SECTIONS = (
    "assumptions", "profit", "depreciation", "working_capital", "loan_schedule",
    "cash_flow", "irr_npv", "balance_sheet", "ratios", "validation", "metadata",
)


def build_financial_model(engine_output: dict) -> dict:
    """Reshape run_financial_engine() output into the canonical FinancialModel dict.

    Returns {metadata, assumptions, financials{profit, balance_sheet, cash_flow,
    ratios, irr_npv}, supporting_schedules{depreciation, working_capital,
    loan_schedule}, validation}. Raises ValueError if engine_output is not a dict or
    is missing a required section.
    """
    if not isinstance(engine_output, dict):
        raise ValueError(f"build_financial_model: engine_output must be a dict, "
                         f"got {type(engine_output).__name__}")

    missing = [s for s in _REQUIRED_SECTIONS
               if s not in engine_output or engine_output[s] is None]
    if missing:
        raise ValueError(f"build_financial_model: engine_output is missing required "
                         f"section(s): {', '.join(missing)}")

    # Reference the existing objects verbatim — no copy, no transformation, so values
    # are byte-for-byte what the engine produced.
    return {
        "metadata": engine_output["metadata"],
        "assumptions": engine_output["assumptions"],
        "financials": {
            "profit": engine_output["profit"],
            "balance_sheet": engine_output["balance_sheet"],
            "cash_flow": engine_output["cash_flow"],
            "ratios": engine_output["ratios"],
            "irr_npv": engine_output["irr_npv"],
        },
        "supporting_schedules": {
            "depreciation": engine_output["depreciation"],
            "working_capital": engine_output["working_capital"],
            "loan_schedule": engine_output["loan_schedule"],
        },
        "validation": engine_output["validation"],
    }
