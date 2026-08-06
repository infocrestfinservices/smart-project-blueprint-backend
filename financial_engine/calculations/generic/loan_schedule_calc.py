"""
loan_schedule_calc.py

Industry-agnostic term-loan amortisation. A line-for-line mirror of the Bank Loan
CMA workbook's **Repayment** sheet — the CORRECTED version of it.

The Excel formulas being reproduced (columns C..G = Years 1..5):

    r5  Opening balance   C5 = Assumptions!$C$8        (loan);  D5 = C8 (prior closing)
    r6  Interest for year C6 = C5 * Assumptions!$C$10   (opening balance x rate)
    r7  Principal repaid  C7 = IF(1 <= Assumptions!$C$12/12, 0,
                                  MIN(C5, IFERROR(Assumptions!$C$8
                                       / (Assumptions!$C$11/12 - Assumptions!$C$12/12), 0)))
    r8  Closing balance   C8 = C5 - C7

Mapped to schema field names (assumption_schema.json):

    C8  term_loan_amount        C10 interest_rate_term_loan
    C11 term_loan_tenure_months C12 moratorium_months

IMPORTANT — this mirrors the FIXED formula. The template originally had
`C11 - C12/12`, which subtracted YEARS from MONTHS: with a 60-month tenure and a
6-month moratorium the denominator came out as 59.5 (months treated as years), so
annual principal was loan/59.5 instead of loan/4.5 — roughly 13x too small, leaving
91.6% of a 5-year loan outstanding after 5 years and inflating every DSCR the
platform produced. The template's Repayment!C7:G7 now reads `C11/12 - C12/12`, and
this module deliberately reproduces that corrected behaviour, NOT the old bug.

Model characteristics, all inherited from the Excel on purpose:

  * Equal annual principal (straight-line amortisation), NOT a level-EMI schedule.
    There is no PMT/annuity anywhere in the sheet.
  * Interest on the REDUCING balance: each year's interest is that year's OPENING
    balance x the rate, so interest falls as principal is repaid.
  * The moratorium suppresses PRINCIPAL only — interest still accrues and is
    charged during the moratorium years.
  * MIN(opening, instalment) caps the final payment so the balance lands exactly on
    zero and never goes negative.
  * The schedule covers the 5-year projection horizon only. A tenure longer than 5
    years legitimately leaves a closing balance outstanding at Year 5.

Pure functions: no I/O, no AI, no Excel, no file access.
"""

MONTHS_PER_YEAR = 12
YEARS = 5

_REQUIRED_KEYS = (
    "term_loan_amount",
    "interest_rate_term_loan",
    "term_loan_tenure_months",
    "moratorium_months",
)


def _require(assumptions: dict, keys, fn_name: str) -> None:
    """Fail loudly and early. A missing key must never become a silent 0 that
    propagates through the model as a plausible-looking wrong number."""
    if not isinstance(assumptions, dict):
        raise ValueError(f"{fn_name}: assumptions must be a dict, got {type(assumptions).__name__}")
    missing = [k for k in keys if assumptions.get(k) is None]
    if missing:
        raise ValueError(
            f"{fn_name}: missing required assumption field(s): {', '.join(missing)}. "
            f"These must be present in the assumptions dict (see assumption_schema.json)."
        )


def _num(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field!r} must be numeric, got {value!r}")


def calculate_loan_schedule(assumptions: dict) -> dict:
    """{"opening_balance": [5], "interest": [5], "principal": [5], "closing_balance": [5]}

    One entry per projection year. Mirrors Repayment rows 5-8 exactly, using the
    CORRECTED principal denominator (tenure_months/12 - moratorium_months/12).
    """
    _require(assumptions, _REQUIRED_KEYS, "calculate_loan_schedule")

    loan = _num(assumptions["term_loan_amount"], "term_loan_amount")
    rate = _num(assumptions["interest_rate_term_loan"], "interest_rate_term_loan")
    tenure_months = _num(assumptions["term_loan_tenure_months"], "term_loan_tenure_months")
    moratorium_months = _num(assumptions["moratorium_months"], "moratorium_months")

    tenure_years = tenure_months / MONTHS_PER_YEAR
    moratorium_years = moratorium_months / MONTHS_PER_YEAR
    repayment_years = tenure_years - moratorium_years

    # Excel: IFERROR(loan / (tenure_yrs - moratorium_yrs), 0) — a non-positive
    # denominator makes the division error, and IFERROR turns it into 0.
    instalment = (loan / repayment_years) if repayment_years > 0 else 0.0

    opening_balance, interest, principal, closing_balance = [], [], [], []
    opening = loan
    for year in range(1, YEARS + 1):
        yr_interest = opening * rate                       # reducing balance
        # Excel: IF(year <= moratorium_years, 0, MIN(opening, instalment))
        yr_principal = 0.0 if year <= moratorium_years else min(opening, instalment)
        closing = opening - yr_principal

        opening_balance.append(opening)
        interest.append(yr_interest)
        principal.append(yr_principal)
        closing_balance.append(closing)
        opening = closing                                   # next year's opening

    return {
        "opening_balance": opening_balance,
        "interest": interest,
        "principal": principal,
        "closing_balance": closing_balance,
    }


def monthly_interest_series(assumptions: dict) -> list:
    """60 monthly term-loan interest values. Mirrors Expenses!row 14, which is
    `Repayment!<year>6 / 12` — the year's total interest spread flat across its 12
    months, stepping down once a year as the balance amortises."""
    schedule = calculate_loan_schedule(assumptions)
    out = []
    for yr_interest in schedule["interest"]:
        out.extend([yr_interest / MONTHS_PER_YEAR] * MONTHS_PER_YEAR)
    return out


def total_debt_obligation(assumptions: dict) -> list:
    """Annual debt service = principal + interest, per year. This is the DSCR
    sheet's 'Total Debt Obligation (B)' line (DSCR!r13 = r11 + r12).

    Note it uses TERM-LOAN interest only — working-capital interest is treated as an
    operating cost and is deliberately excluded from debt service, which is the
    conventional CA treatment.
    """
    s = calculate_loan_schedule(assumptions)
    return [p + i for p, i in zip(s["principal"], s["interest"])]
