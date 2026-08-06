"""
loan_amortization_calc.py

Generic, reusable loan amortization calculator.

Named loan_amortization_calc (NOT loan_schedule_calc) because a different module,
loan_schedule_calc.py, already exists in this package: that one is an Excel-mirror
that produces the CMA workbook's ANNUAL, equal-principal 5-year schedule from a
BusinessProfile-style assumptions dict. This module is the fully GENERIC amortizer:
explicit numeric inputs, MONTHLY schedule, EMI or equal-principal, principal
moratorium, and totals. The two are intentionally separate and both are kept.

This module knows nothing about Bank Loan, Feasibility, Government Grant, or any Excel
template. It is a pure numeric calculator that the future Cash Flow Engine and every
report-purpose pipeline can consume. No external finance libraries — standard library
only.

Rounding policy: all intermediate arithmetic is done in full-precision float; monetary
values are rounded to 2 decimals ONLY when building the returned output, so there is
no cumulative rounding drift. The final month's principal is adjusted so the closing
balance is exactly zero.
"""

from __future__ import annotations

from typing import List, Optional

# A rate above this is almost certainly a percentage (12) passed where a decimal
# fraction (0.12) was expected. 1.5 == 150% p.a., implausible for a real loan.
_MAX_PLAUSIBLE_RATE = 1.5
_SUPPORTED_TYPES = ("emi", "equal_principal")


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def _r2(x: float) -> float:
    """Round a monetary value to 2 dp for output, normalising -0.0 to 0.0."""
    v = round(x, 2)
    return 0.0 if v == 0 else v


def calculate_loan_schedule(
    assumptions: dict,
    loan_amount: float,
    annual_interest_rate: float,
    tenure_years: int,
    moratorium_months: int = 0,
    repayment_type: str = "emi",
) -> dict:
    """Compute a loan's monthly + annual repayment schedule and totals.

    Args:
        assumptions: reserved pass-through for caller context; must be a dict but no
            keys are required (all numeric inputs are explicit params).
        loan_amount: principal, > 0.
        annual_interest_rate: decimal fraction (0.12 == 12%), NOT a percentage.
        tenure_years: total loan life in years, > 0.
        moratorium_months: leading months of principal holiday (interest still paid),
            >= 0 and < tenure in months.
        repayment_type: "emi" (level payment, reducing balance) or "equal_principal"
            (constant principal, reducing interest).

    Returns the structure documented in the module/spec: monthly_schedule,
    annual_schedule, total_interest, total_principal, total_payment,
    effective_interest_rate.
    """
    fn = "calculate_loan_schedule"

    # -- validation (loud and early, same style as the other modules) --
    if not isinstance(assumptions, dict):
        raise ValueError(f"{fn}: assumptions must be a dict, got {type(assumptions).__name__}")

    loan_amount = _num(loan_amount, "loan_amount")
    if loan_amount <= 0:
        raise ValueError(f"{fn}: loan_amount must be > 0, got {loan_amount}")

    annual_interest_rate = _num(annual_interest_rate, "annual_interest_rate")
    if annual_interest_rate < 0:
        raise ValueError(f"{fn}: annual_interest_rate must be >= 0, got {annual_interest_rate}")
    if annual_interest_rate > _MAX_PLAUSIBLE_RATE:
        raise ValueError(
            f"{fn}: annual_interest_rate={annual_interest_rate} looks like a percentage. "
            f"Pass a decimal fraction, e.g. 0.12 for 12% (must be <= {_MAX_PLAUSIBLE_RATE}).")

    if not isinstance(tenure_years, int) or isinstance(tenure_years, bool):
        raise ValueError(f"{fn}: tenure_years must be an int, got {tenure_years!r}")
    if tenure_years <= 0:
        raise ValueError(f"{fn}: tenure_years must be > 0, got {tenure_years}")

    if not isinstance(moratorium_months, int) or isinstance(moratorium_months, bool):
        raise ValueError(f"{fn}: moratorium_months must be an int, got {moratorium_months!r}")
    if moratorium_months < 0:
        raise ValueError(f"{fn}: moratorium_months must be >= 0, got {moratorium_months}")

    if repayment_type not in _SUPPORTED_TYPES:
        raise ValueError(
            f"{fn}: unsupported repayment_type {repayment_type!r}; "
            f"supported: {', '.join(_SUPPORTED_TYPES)}")

    total_months = tenure_years * 12
    if moratorium_months >= total_months:
        raise ValueError(
            f"{fn}: moratorium_months ({moratorium_months}) must be less than the tenure "
            f"in months ({total_months}); there would be no time left to repay principal.")

    repayment_months = total_months - moratorium_months
    monthly_rate = annual_interest_rate / 12.0

    # -- pre-compute the fixed instalment / fixed principal (full precision) --
    if repayment_type == "emi":
        if monthly_rate == 0:
            emi = loan_amount / repayment_months          # zero-interest: pure principal
        else:
            factor = (1.0 + monthly_rate) ** repayment_months
            emi = loan_amount * monthly_rate * factor / (factor - 1.0)
        fixed_principal = None
    else:  # equal_principal
        emi = None
        fixed_principal = loan_amount / repayment_months

    # -- build the month-by-month schedule in full precision --
    monthly: List[dict] = []
    balance = loan_amount
    for month in range(1, total_months + 1):
        opening = balance
        interest = opening * monthly_rate
        in_moratorium = month <= moratorium_months
        is_final = month == total_months

        if in_moratorium:
            principal = 0.0
            payment = interest                            # interest-only servicing
        elif repayment_type == "emi":
            if is_final:
                principal = opening                       # clear any residual exactly
                payment = principal + interest
            else:
                principal = emi - interest
                payment = emi
        else:  # equal_principal
            principal = opening if is_final else fixed_principal
            payment = principal + interest

        closing = opening - principal
        if abs(closing) < 1e-9:
            closing = 0.0                                 # kill float dust

        monthly.append({
            "month": month,
            "opening_balance": _r2(opening),
            "interest": _r2(interest),
            "principal": _r2(principal),
            "emi": _r2(payment),
            "closing_balance": _r2(closing),
            # full-precision copies retained privately for exact annual/total sums
            "_i": interest, "_p": principal, "_pay": payment, "_close": closing,
        })
        balance = closing

    # -- annual roll-up (12 months per year), summed from full precision --
    annual: List[dict] = []
    for y in range(tenure_years):
        block = monthly[y * 12:(y + 1) * 12]
        yi = sum(r["_i"] for r in block)
        yp = sum(r["_p"] for r in block)
        annual.append({
            "year": y + 1,
            "interest": _r2(yi),
            "principal": _r2(yp),
            "total_payment": _r2(yi + yp),
            "closing_balance": _r2(block[-1]["_close"]),
        })

    total_interest = sum(r["_i"] for r in monthly)
    total_principal = sum(r["_p"] for r in monthly)
    total_payment = total_interest + total_principal

    # Effective annual rate from monthly compounding (nominal -> effective).
    effective_interest_rate = (1.0 + monthly_rate) ** 12 - 1.0

    # strip the private full-precision helpers from the public output
    for r in monthly:
        for k in ("_i", "_p", "_pay", "_close"):
            r.pop(k, None)

    return {
        "monthly_schedule": monthly,
        "annual_schedule": annual,
        "total_interest": _r2(total_interest),
        "total_principal": _r2(total_principal),
        "total_payment": _r2(total_payment),
        "effective_interest_rate": round(effective_interest_rate, 6),
    }
