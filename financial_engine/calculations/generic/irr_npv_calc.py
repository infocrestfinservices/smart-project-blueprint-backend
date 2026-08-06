"""
irr_npv_calc.py

Standard feasibility-study investment metrics — IRR, NPV, simple & discounted
payback, and profitability index — from a project's cash-flow series.

This module is INDUSTRY- AND PURPOSE-AGNOSTIC (same shape as the other generic
calculators): it takes numbers in and returns numbers out. It performs no AI, no
Excel, no I/O.

Unlike the other generic modules, it is NOT a mirror of an existing Excel sheet — the
Bank Loan CMA workbook contains no IRR/NPV/discount cells. It is a fresh, standalone
computation for feasibility-style appraisals, verified against hand-computed
finance-textbook values in test_irr_npv_manual.py (not merely against itself).

IRR SOLVER
----------
numpy_financial.irr is the usual choice but is not installed here (and not in
requirements.txt). Rather than add a dependency silently, IRR is solved in two stages
(see _irr): Newton-Raphson first, bracketed bisection as a fallback.

Why two algorithms — they trade speed for guaranteed convergence, so using both gives
the best of each:

  * Newton-Raphson converges quadratically and nails a conventional project (Year 0
    outflow, later inflows) in a handful of iterations from a sensible guess. But it
    is NOT guaranteed: it can diverge, oscillate, step outside the valid domain
    (rate <= -100%, where the discount factor blows up), or lock onto the wrong root
    when the cash flows change sign more than once. So it is fast but fragile.

  * Bisection is slower (linear convergence) but, once a sign change of NPV(rate)
    brackets a root, it ALWAYS converges to it. For a conventional project NPV is
    monotonic in the rate, so the root is unique and bisection is bullet-proof.

So the solver tries the fast method first and only pays for the robust one when the
fast method fails. If no sign change exists at all (e.g. all-positive or all-negative
cash flows) there is no real IRR, and IRR is None — it never returns 0 or a garbage
value to paper over non-convergence.

Recommendation (not applied): add `numpy-financial` to requirements.txt if you would
prefer the library's vectorised irr/npv. This module does not require it.

Pure functions: dict/list in, dict out.
"""

from __future__ import annotations

from typing import List, Optional

# A discount rate above this is almost certainly a percentage (e.g. 12) passed where a
# decimal fraction (0.12) was expected. 1.5 = 150% p.a., implausible for a real rate.
_MAX_PLAUSIBLE_RATE = 1.5


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def npv(discount_rate: float, cash_flows: List[float]) -> float:
    """Net present value of a cash-flow series at `discount_rate` (decimal fraction).
    cash_flows[t] is discounted by (1 + rate)**t, so index 0 is undiscounted (Year 0).
    """
    total = 0.0
    for t, cf in enumerate(cash_flows):
        total += cf / ((1.0 + discount_rate) ** t)
    return total


def _npv_and_slope(rate: float, cash_flows: List[float]):
    """NPV(rate) and its first derivative d(NPV)/d(rate), computed together in one
    pass (Newton-Raphson needs both). Derivative of cf_t / (1+rate)**t is
    -t * cf_t / (1+rate)**(t+1)."""
    value = 0.0
    slope = 0.0
    for t, cf in enumerate(cash_flows):
        factor = (1.0 + rate) ** t
        value += cf / factor
        if t > 0:
            slope += -t * cf / ((1.0 + rate) ** (t + 1))
    return value, slope


def _irr_newton(cash_flows: List[float], guess: float = 0.1,
                tol: float = 1e-9, max_iter: int = 100) -> Optional[float]:
    """IRR via Newton-Raphson. Fast (quadratic) but not guaranteed — returns None
    (so the caller falls back to bisection) whenever it cannot be trusted: a
    (near-)zero derivative, a step outside the valid domain (rate <= -1), or failure
    to reach NPV == 0 within max_iter. A returned value is always re-checked to
    genuinely zero the NPV, so a spurious 'converged' point is rejected too."""
    rate = guess
    for _ in range(max_iter):
        value, slope = _npv_and_slope(rate, cash_flows)
        if abs(value) < tol:
            return rate
        if abs(slope) < 1e-12:            # flat -> Newton would divide by ~0; bail out
            return None
        step = value / slope
        rate = rate - step
        if rate <= -1.0:                  # left the valid domain (discount factor blows up)
            return None
        if abs(step) < tol:
            break
    # Only accept if the final rate actually zeroes the NPV (guards against a
    # small-step stop that isn't a real root).
    return rate if abs(npv(rate, cash_flows)) < 1e-6 else None


def _irr_bisection(cash_flows: List[float], tol: float = 1e-9,
                   max_iter: int = 500) -> Optional[float]:
    """IRR via bracketed bisection — the robust fallback. Returns the rate where
    NPV == 0, or None if no real root exists in the searched range. Never returns a
    non-converged value."""
    def f(r: float) -> float:
        return npv(r, cash_flows)

    # Scan rates for a sign change to bracket the root. Lower bound just above -100%
    # (rate = -1 makes the discount factor blow up); scan upward through plausible and
    # then large rates so even very high-return projects are bracketed.
    lo = -0.999999
    f_lo = f(lo)
    if abs(f_lo) < tol:
        return lo

    prev_r, prev_f = lo, f_lo
    r = -0.99
    while r <= 1e6:
        cur_f = f(r)
        if abs(cur_f) < tol:
            return r
        if (prev_f < 0) != (cur_f < 0):  # sign change -> root is in (prev_r, r)
            a, b, fa = prev_r, r, prev_f
            for _ in range(max_iter):
                m = (a + b) / 2.0
                fm = f(m)
                if abs(fm) < tol or (b - a) / 2.0 < tol:
                    return m
                if (fa < 0) != (fm < 0):
                    b = m
                else:
                    a, fa = m, fm
            return (a + b) / 2.0
        prev_r, prev_f = r, cur_f
        # step: fine through the normal range, then grow geometrically
        r = (r + 0.01) if r < 1.0 else (r * 1.5)
    return None  # no bracket found -> no real IRR in a sane range


def _irr(cash_flows: List[float]) -> Optional[float]:
    """Internal-rate-of-return: try the fast method, fall back to the robust one.

      1. Precheck — a real IRR requires at least one sign change in the cash flows;
         without one (all-positive or all-negative) there is no root, so return None
         immediately rather than let either solver chase a non-existent one.
      2. Newton-Raphson — fast; used first.
      3. Bisection — guaranteed once a root is bracketed; used only if Newton fails.
      4. None — if neither finds a valid root.
    """
    has_pos = any(cf > 0 for cf in cash_flows)
    has_neg = any(cf < 0 for cf in cash_flows)
    if not (has_pos and has_neg):
        return None

    newton = _irr_newton(cash_flows)
    if newton is not None:
        return newton
    return _irr_bisection(cash_flows)


def calculate_irr_npv_payback(
    assumptions: dict,
    cash_flow_series: List[float],
    initial_investment: float,
    discount_rate: float,
    project_life_years: int = 5,
) -> dict:
    """Feasibility metrics from a project's cash-flow series.

    cash_flow_series: typically Year 0 = -initial_investment, Years 1..N = net cash
      flow each year (e.g. PAT + depreciation - change in working capital, or whatever
      the caller computes). Index t is discounted by (1+discount_rate)**t.
    initial_investment: the up-front outflow (positive number), used for payback and
      the profitability index.
    discount_rate: decimal fraction (0.12 == 12%), NOT a percentage.

    Returns {irr, npv, payback_period_years, discounted_payback_years,
             profitability_index}. irr / payback fields are None when undefined
             rather than a misleading 0.
    """
    fn = "calculate_irr_npv_payback"

    # -- validation (same loud-and-early style as the other modules) --
    if not isinstance(assumptions, dict):
        raise ValueError(f"{fn}: assumptions must be a dict, got {type(assumptions).__name__}")
    if not isinstance(cash_flow_series, (list, tuple)):
        raise ValueError(f"{fn}: cash_flow_series must be a list, got "
                         f"{type(cash_flow_series).__name__}")
    if not isinstance(project_life_years, int) or project_life_years < 1:
        raise ValueError(f"{fn}: project_life_years must be a positive int, got "
                         f"{project_life_years!r}")
    if len(cash_flow_series) < project_life_years + 1:
        raise ValueError(
            f"{fn}: cash_flow_series must have at least project_life_years+1 = "
            f"{project_life_years + 1} entries (Year 0 + {project_life_years} years), "
            f"got {len(cash_flow_series)}.")

    initial_investment = _num(initial_investment, "initial_investment")
    if initial_investment <= 0:
        raise ValueError(f"{fn}: initial_investment must be > 0, got {initial_investment}")

    discount_rate = _num(discount_rate, "discount_rate")
    if discount_rate > _MAX_PLAUSIBLE_RATE:
        raise ValueError(
            f"{fn}: discount_rate={discount_rate} looks like a percentage. Pass a "
            f"decimal fraction, e.g. 0.12 for 12% (must be <= {_MAX_PLAUSIBLE_RATE}).")

    cfs = [_num(cf, f"cash_flow_series[{i}]") for i, cf in enumerate(cash_flow_series)]

    # -- NPV (whole series, Year 0 included) --
    net_present_value = npv(discount_rate, cfs)

    # -- IRR (Newton-Raphson first, bisection fallback; None if no real root) --
    irr = _irr(cfs)

    # -- Simple payback: cumulate the operating inflows (Years 1..N) against the
    #    initial investment. None if never recovered within project_life_years. --
    inflows = cfs[1:project_life_years + 1]
    payback = _payback(inflows, initial_investment, discounted=False, rate=discount_rate)

    # -- Discounted payback: same but each inflow discounted to present value. --
    discounted_payback = _payback(inflows, initial_investment, discounted=True,
                                  rate=discount_rate)

    # -- Profitability index: PV of the operating inflows / initial investment. --
    pv_inflows = sum(cf / ((1.0 + discount_rate) ** (t + 1)) for t, cf in enumerate(inflows))
    profitability_index = pv_inflows / initial_investment

    return {
        "irr": irr,
        "npv": net_present_value,
        "payback_period_years": payback,
        "discounted_payback_years": discounted_payback,
        "profitability_index": profitability_index,
    }


def _payback(inflows: List[float], initial_investment: float,
             discounted: bool, rate: float) -> Optional[float]:
    """Years to recover initial_investment from the (optionally discounted) inflows.
    Linear interpolation within the recovery year. None if never recovered."""
    cumulative = 0.0
    for i, cf in enumerate(inflows):
        year = i + 1
        value = cf / ((1.0 + rate) ** year) if discounted else cf
        if cumulative + value >= initial_investment:
            shortfall = initial_investment - cumulative
            fraction = shortfall / value if value > 0 else 0.0
            return (year - 1) + fraction
        cumulative += value
    return None
