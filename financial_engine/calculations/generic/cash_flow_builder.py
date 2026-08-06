"""
cash_flow_builder.py

Builds a project's yearly cash-flow series from outputs already produced by the other
generic financial modules (profit, depreciation, working capital, loan schedule).

Completely generic: it knows nothing about Bank Loan, Feasibility, VC, Government
Grant, Angel, Immigration, Startup, or Real Estate — and nothing about Excel,
templates, or LibreOffice. It only arithmetically combines numbers it is given.

CASH-FLOW MODEL
---------------
Three activity buckets, plus their sum (all lists are length N+1: Year 0 .. Year N).

  Operating (Years 1..N):   PAT + Depreciation - Increase in Working Capital
  Investing (Year 0):       - Capital Expenditure
  Financing (Year 0):       + Loan Drawdown + Promoter Equity
  Financing (Years 1..N):   - Loan Principal Repayment

  net_cash_flow = operating + investing + financing   (this is cash_flow_series)

NO DOUBLE-COUNTING OF INTEREST
------------------------------
PAT is assumed to be AFTER finance cost (interest already deducted in the P&L). So the
financing bucket contains ONLY principal repayment and Year-0 drawdown/equity — never
interest. Adding interest here would deduct it twice.

WORKING CAPITAL
---------------
working_capital_output supplies the net working-capital LEVEL for each year. The cash
impact is the year-over-year INCREASE (a build-up of WC absorbs cash; a release frees
cash). Year 1's increase is measured against the initial level (default 0, or
assumptions["initial_working_capital"]).

INPUT CONTRACT (with aliases so the real upstream modules plug in directly)
    profit_output           : {"pat": [N]}
    depreciation_output     : {"annual_depreciation" | "depreciation": [N]}
    working_capital_output  : {"working_capital" | "working_capital_gap": [N]}
    loan_schedule_output    : {"principal" | "principal_repayment": [N]}
    assumptions             : capital_expenditure (or the 4 cost components),
                              term_loan_amount (or loan_drawdown),
                              promoters_capital (or promoter_equity),
                              optionally initial_working_capital (default 0)

Pure functions: dicts in, dict out. No I/O.
"""

from __future__ import annotations

from typing import List, Optional

_CAPEX_COMPONENTS = ("land_cost", "building_cost", "plant_machinery_cost", "furniture_other_cost")


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def _require_dict(d, name: str, fn: str) -> None:
    if not isinstance(d, dict):
        raise ValueError(f"{fn}: {name} must be a dict, got {type(d).__name__}")


def _series(d: dict, name: str, aliases, fn: str) -> List[float]:
    """Pull a yearly list from `d` under the first matching alias, validated numeric."""
    for key in aliases:
        if key in d:
            val = d[key]
            if not isinstance(val, (list, tuple)):
                raise ValueError(f"{fn}: {name}[{key!r}] must be a list, got "
                                 f"{type(val).__name__}")
            return [_num(v, f"{name}[{key!r}][{i}]") for i, v in enumerate(val)]
    raise ValueError(f"{fn}: {name} is missing a required key "
                     f"(expected one of: {', '.join(aliases)})")


def _first_present(assumptions: dict, aliases, label: str, fn: str) -> Optional[float]:
    for key in aliases:
        if assumptions.get(key) is not None:
            return _num(assumptions[key], key)
    return None


def _resolve_capex(assumptions: dict, fn: str) -> float:
    """Year-0 capital expenditure: an explicit 'capital_expenditure', else the sum of
    the four project-cost components if all are present."""
    explicit = _first_present(assumptions, ("capital_expenditure", "capex"), "capex", fn)
    if explicit is not None:
        return explicit
    if all(assumptions.get(k) is not None for k in _CAPEX_COMPONENTS):
        return sum(_num(assumptions[k], k) for k in _CAPEX_COMPONENTS)
    raise ValueError(
        f"{fn}: assumptions must provide 'capital_expenditure' (or all four cost "
        f"components: {', '.join(_CAPEX_COMPONENTS)}).")


def build_cash_flow_series(
    assumptions: dict,
    profit_output: dict,
    depreciation_output: dict,
    working_capital_output: dict,
    loan_schedule_output: dict,
) -> dict:
    """Build the yearly project cash-flow series and its activity decomposition.

    Returns {cash_flow_series, operating_cash_flow, financing_cash_flow,
    investing_cash_flow, net_cash_flow}, each a list of length N+1 (Year 0..Year N).
    cash_flow_series is identical to net_cash_flow.
    """
    fn = "build_cash_flow_series"

    # -- validation: every argument must be a dict --
    _require_dict(assumptions, "assumptions", fn)
    _require_dict(profit_output, "profit_output", fn)
    _require_dict(depreciation_output, "depreciation_output", fn)
    _require_dict(working_capital_output, "working_capital_output", fn)
    _require_dict(loan_schedule_output, "loan_schedule_output", fn)

    # -- pull the four yearly series (length N each) --
    pat = _series(profit_output, "profit_output", ("pat",), fn)
    dep = _series(depreciation_output, "depreciation_output",
                  ("annual_depreciation", "depreciation"), fn)
    wc_level = _series(working_capital_output, "working_capital_output",
                       ("working_capital", "working_capital_gap"), fn)
    principal = _series(loan_schedule_output, "loan_schedule_output",
                        ("principal", "principal_repayment"), fn)

    # -- yearly series lengths must all match, and be non-empty --
    lengths = {"profit_output.pat": len(pat), "depreciation_output": len(dep),
               "working_capital_output": len(wc_level), "loan_schedule_output": len(principal)}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"{fn}: yearly series lengths differ: {lengths}")
    n_years = len(pat)
    if n_years < 1:
        raise ValueError(f"{fn}: yearly series must have at least 1 year, got {n_years}")

    # -- Year-0 inputs from assumptions --
    capex = _resolve_capex(assumptions, fn)
    loan_drawdown = _first_present(assumptions, ("term_loan_amount", "loan_drawdown"),
                                   "loan_drawdown", fn)
    if loan_drawdown is None:
        raise ValueError(f"{fn}: assumptions must provide 'term_loan_amount' (or 'loan_drawdown').")
    promoter_equity = _first_present(assumptions, ("promoters_capital", "promoter_equity"),
                                     "promoter_equity", fn)
    if promoter_equity is None:
        raise ValueError(f"{fn}: assumptions must provide 'promoters_capital' (or 'promoter_equity').")
    initial_wc = _first_present(assumptions, ("initial_working_capital",), "initial_wc", fn) or 0.0

    # -- year-over-year increase in working capital (WC build-up absorbs cash) --
    increase_in_wc = []
    prev = initial_wc
    for level in wc_level:
        increase_in_wc.append(level - prev)
        prev = level

    # -- assemble the three buckets, indexed 0..N (Year 0 prepended) --
    operating = [0.0]                                  # no operations in Year 0
    investing = [-capex]                               # Year-0 capex outflow
    financing = [loan_drawdown + promoter_equity]      # Year-0 drawdown + equity
    for t in range(n_years):
        operating.append(pat[t] + dep[t] - increase_in_wc[t])   # PAT + Dep - dWC
        investing.append(0.0)                                   # no further capex here
        financing.append(-principal[t])                         # principal only (no interest)

    net = [o + i + f for o, i, f in zip(operating, investing, financing)]

    return {
        "cash_flow_series": list(net),   # == net_cash_flow, kept as the headline series
        "operating_cash_flow": operating,
        "financing_cash_flow": financing,
        "investing_cash_flow": investing,
        "net_cash_flow": net,
    }
