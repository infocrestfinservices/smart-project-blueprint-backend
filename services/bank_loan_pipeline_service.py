"""
bank_loan_pipeline_service.py

End-to-end orchestration of the Bank Loan report:

    industry/purpose/user_details
      -> generate_assumptions()          (assumption_architect_service)   AI
      -> map_assumptions_to_template()   (assumption_mapper)              44 -> 59 cells
      -> fill_template()                 (template_fill_service)          writes the xlsx
      -> recalculate_xlsx()              (recalc_service)                 LibreOffice
      -> DSCR viability check (retry once if the model can't service its debt)
      -> generated_reports/<name>.xlsx

Pure orchestration: every step is an existing service. No provider config, no cell
writing, no LibreOffice invocation is reimplemented here.

Not wired to any router — nothing imports this yet. Call it directly.
"""

import io
import logging
import os
import re
from datetime import datetime

from openpyxl import load_workbook

from template_config import find_template_by_id
from services.assumption_architect_service import generate_assumptions
from services.assumption_mapper import map_assumptions_to_template
from services.template_fill_service import fill_template
from services.recalc_service import recalculate_xlsx, libreoffice_available

logger = logging.getLogger("bank_loan_pipeline")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BACKEND_DIR, "generated_reports")

TEMPLATE_ID = "bank_loan_cma"

# Ratios!C15 is Year-1 DSCR: row 15 is labelled "DSCR" (B15) and column C is
# "Year 1" (C4). Below 1.2 the business cannot comfortably service its debt and no
# bank would accept the CMA, so we give the AI one more attempt.
DSCR_SHEET = "Ratios"
DSCR_CELL = "C15"
DSCR_MIN = 1.2

# Scaling the AI's own capacity by more than this to make the loan serviceable means
# the loan is large relative to the business the AI actually described. The report is
# still produced, but flagged for human review.
IMPLAUSIBLE_SCALING = 2.5

# The opposite problem from DSCR_MIN: a DSCR this high means the loan is tiny next to
# the business's revenue scale, which usually means the AI under-sized the loan rather
# than that the business is spectacular. Informational only — a bank is not harmed by
# an oversized safety margin, so this never triggers a retry.
DSCR_CEILING = 20.0


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or "report"


def _output_name(industry: str, purpose: str) -> str:
    """e.g. manufacturing_bank_loan_20260713_153455.xlsx — timestamped, so a rerun
    never overwrites a previous report."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_slug(industry)}_{_slug(purpose)}_{stamp}.xlsx"


def _read_dscr(xlsx: bytes):
    """Year-1 DSCR from a recalculated workbook, or None if it has no cached value
    (i.e. recalc did not run) or the read fails. None means 'unknown', not 'zero'."""
    try:
        wb = load_workbook(io.BytesIO(xlsx), data_only=True)
        try:
            v = wb[DSCR_SHEET][DSCR_CELL].value
        finally:
            wb.close()
    except Exception as e:
        logger.warning("could not read %s!%s: %s", DSCR_SHEET, DSCR_CELL, e)
        return None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# target_dscr is set well above the real 1.2 floor because this simplified formula
# ignores tax, working-capital interest, moratorium effects on Year-1 principal, and
# the real depreciation schedule — all of which the actual template accounts for.
# Empirically, the formula's estimate has run ~2.0 points more optimistic than the
# template's real recalculated DSCR, so the higher target compensates for that gap.
# The existing retry-with-real-DSCR safety net in run_bank_loan_pipeline() remains
# the final backstop regardless of this estimate's accuracy.
def _fix_capacity_for_viability(assumptions: dict, target_dscr: float = 3.5):
    """The AI is good at unit economics (price/costs/benchmarks) but unreliable at
    multi-step arithmetic, so it sometimes picks an installed_capacity too small to
    service the loan it also picked. This deterministically computes the MINIMUM
    installed_capacity needed to hit target_dscr in Year 1, given the AI's own
    price/cost/loan figures, and raises installed_capacity to that minimum if the
    AI's original value falls short. Never lowers it.

    Returns (assumptions, diagnostics). `assumptions` is a NEW dict — the input is
    never mutated. `diagnostics` records whether the guard fired and by how much: a
    large scaling multiplier means the loan is big relative to the business the AI
    actually described, which a human should look at before trusting the report.
    """
    a = dict(assumptions)  # don't mutate the caller's dict
    original_capacity = a.get("installed_capacity", 0)

    def _diag(fired: bool, final):
        multiplier = (final / original_capacity) if (fired and original_capacity) else None
        return {
            "capacity_guard_fired": fired,
            "original_capacity": original_capacity if fired else None,
            "final_capacity": final,
            "scaling_multiplier": multiplier,
            "flagged_implausible": multiplier is not None and multiplier > IMPLAUSIBLE_SCALING,
        }

    price = a.get("selling_price_y1", 0)
    cost1 = a.get("cost1_per_unit_y1", 0)
    cost2 = a.get("cost2_per_unit_y1", 0)
    other = a.get("other_variable_cost_y1", 0)
    contribution = price - cost1 - cost2 - other

    if contribution <= 0:
        # Not a capacity problem — the per-unit economics themselves are broken
        # (Rule 6 is supposed to prevent this). Leave capacity as-is; the existing
        # DSCR retry-guard will still catch this downstream.
        return a, _diag(False, original_capacity)

    fixed_monthly = (a.get("wages_monthly_y1", 0) + a.get("factory_overheads_monthly_y1", 0)
                     + a.get("repairs_maintenance_monthly_y1", 0)
                     + a.get("admin_expenses_monthly_y1", 0))
    annual_fixed = fixed_monthly * 12

    loan = a.get("term_loan_amount", 0)
    rate = a.get("interest_rate_term_loan", 0)
    tenure_years = max(a.get("term_loan_tenure_months", 60) / 12, 1)
    annual_debt = loan * rate + loan / tenure_years

    if annual_debt <= 0:
        # No debt to service, so "capacity required to reach target DSCR" is meaningless
        # — solving for it just chases an unreachable target and inflates capacity
        # (a zero term_loan_amount once produced a bogus 7x scale-up). Leave capacity
        # alone; the term_loan_amount retry-guard in run_bank_loan_pipeline() handles
        # the real problem, which is the missing loan.
        logger.warning("capacity guard: annual debt obligation is 0 "
                       "(term_loan_amount=%s) — skipping capacity sizing", loan)
        return a, _diag(False, original_capacity)

    dep_addback = (a.get("building_cost", 0) * a.get("building_dep_rate", 0)
                   + a.get("plant_machinery_cost", 0) * a.get("plant_machinery_dep_rate", 0)
                   + a.get("furniture_other_cost", 0) * a.get("furniture_dep_rate", 0))

    util_y1 = (a.get("capacity_utilisation_y1_y5") or [0.6])[0]
    if util_y1 <= 0:
        return a, _diag(False, original_capacity)

    # Solve: (contribution * capacity * util_y1 - annual_fixed + dep_addback) / annual_debt >= target_dscr
    required_units_sold = (target_dscr * annual_debt + annual_fixed - dep_addback) / contribution
    required_capacity = required_units_sold / util_y1

    if required_capacity > original_capacity:
        # Round up to the nearest 1,000 for a clean, realistic-looking number.
        new_capacity = int((required_capacity // 1000 + 1) * 1000)
        logger.info(
            "capacity guard: raising installed_capacity %s -> %s "
            "(price=%.2f cost1=%.2f cost2=%.2f other=%.2f contribution=%.2f, "
            "annual_fixed=%.0f, annual_debt=%.0f, target_dscr=%.1f)",
            original_capacity, new_capacity, price, cost1, cost2, other,
            contribution, annual_fixed, annual_debt, target_dscr)
        a["installed_capacity"] = new_capacity
        return a, _diag(True, new_capacity)

    return a, _diag(False, original_capacity)


def _attempt(purpose_key: str, industry: str, purpose: str, user_details: str) -> dict:
    """One full AI -> map -> fill -> recalc pass. Returns the workbook BYTES plus its
    Year-1 DSCR; nothing is written to disk here, so a losing attempt costs no file."""
    assumptions = generate_assumptions(industry, purpose, user_details)
    assumptions, capacity_diag = _fix_capacity_for_viability(assumptions)
    cell_answers = map_assumptions_to_template(assumptions)
    xlsx = fill_template(purpose_key, TEMPLATE_ID, cell_answers)

    # Formula RESULTS only exist once a spreadsheet app opens the file. Recalc is
    # best-effort: without LibreOffice the workbook is still valid and correct, it
    # just carries no cached results until Excel opens it.
    recalculated = False
    if libreoffice_available():
        try:
            xlsx = recalculate_xlsx(xlsx)
            recalculated = True
        except Exception as e:
            logger.warning("recalc failed, keeping un-recalculated workbook: %s", e)
    else:
        logger.warning("LibreOffice not available; no server-side recalc")

    return {
        "assumptions": assumptions,
        "xlsx": xlsx,
        "recalculated": recalculated,
        "dscr": _read_dscr(xlsx) if recalculated else None,
        "filled": sum(1 for k, v in cell_answers.items() if "!" in k and v not in (None, "")),
        "capacity_diag": capacity_diag,
    }


# A working-capital facility has no principal repayment schedule, so DSCR — the metric
# this whole template is built around — is undefined for it. When the user asks only for
# working capital, the AI correctly sets term_loan_amount=0, and the honest answer is to
# say so rather than ship a DSCR=0 workbook. Deliberately narrow: any hint of capex means
# there IS a term loan to appraise, so we fall through to the normal pipeline.
_WC_PHRASES = ("working capital",)
_CAPEX_WORDS = ("machine", "equipment", "expansion", "building", "construction", "purchase")


def _is_working_capital_only(user_details: str) -> bool:
    """True only for an unambiguous working-capital-only request: WC language present,
    no capital-expenditure language anywhere. Keyword heuristic, no AI call."""
    text = (user_details or "").lower()
    if not any(p in text for p in _WC_PHRASES):
        return False
    return not any(w in text for w in _CAPEX_WORDS)


WORKING_CAPITAL_ONLY_MESSAGE = (
    "This report generator currently appraises TERM LOANS (financing for machinery, "
    "construction, expansion, or other capital expenditure) using Debt Service Coverage "
    "Ratio (DSCR) as the core viability metric. Your request describes a "
    "working-capital-only facility, which does not have a term-loan repayment schedule, "
    "so DSCR does not apply to it. Please describe a specific capital expenditure (new "
    "machinery, construction, equipment, expansion, etc.) that this loan will fund, or "
    "contact us about working-capital/MPBF assessment separately."
)


def _loan_invalid(attempt: dict) -> bool:
    """True if the attempt carries no real term loan. A Bank Loan CMA exists to appraise
    a specific facility, so a 0/missing term_loan_amount makes the whole model
    meaningless — and DSCR degenerates to 0/0, which must never read as viable."""
    loan = (attempt.get("assumptions") or {}).get("term_loan_amount")
    if not isinstance(loan, (int, float)) or isinstance(loan, bool):
        return True
    return loan <= 0


def _better(a: dict, b: dict) -> dict:
    """The attempt with the higher Year-1 DSCR. An unknown DSCR (None) always loses
    to a known one; if both are unknown we keep the first."""
    if b["dscr"] is None:
        return a
    if a["dscr"] is None:
        return b
    return b if b["dscr"] > a["dscr"] else a


def run_bank_loan_pipeline(industry: str, purpose: str, user_details: str) -> dict:
    """Generate a complete, recalculated Bank Loan workbook.

    If the first attempt's Year-1 DSCR is below DSCR_MIN the AI is asked once more
    (a single retry, not a loop) and the better of the two workbooks is returned. A
    file is ALWAYS produced — a still-unviable model comes back flagged
    "viable": false rather than as an error.

    Returns {success, report_path, filename, assumptions, recalculated, cells_filled,
    dscr_year1, viable}. Raises ValueError if the template is not registered, and
    propagates the AI's ValueError if it returns unparseable JSON.
    """
    purpose_key, template = find_template_by_id(TEMPLATE_ID)
    if not template:
        raise ValueError(f"Template '{TEMPLATE_ID}' is not registered")

    best = _attempt(purpose_key, industry, purpose, user_details)

    # The AI zeroed the term loan AND the user only ever asked for working capital — so
    # it was right to: a WC facility has no repayment schedule and DSCR is undefined.
    # Retrying cannot fix a correct answer, so bail out early with an explanation rather
    # than writing a meaningless DSCR=0 workbook. No file, no retry, no DSCR check.
    if _loan_invalid(best) and _is_working_capital_only(user_details):
        logger.warning("bank-loan pipeline: working-capital-only request (%s) — no term loan "
                       "to appraise; returning early without generating a report.", industry)
        return {
            "success": False,
            "reason": "working_capital_only",
            "message": WORKING_CAPITAL_ONLY_MESSAGE,
        }

    # Retry on either failure mode. Low DSCR: only when we have a real number that is
    # genuinely too low — a None DSCR means recalc never ran, so a second attempt could
    # not be compared and would just burn another AI call. Invalid loan: the model has
    # no facility to appraise, which is fatal regardless of what DSCR read as.
    low_dscr = best["dscr"] is not None and best["dscr"] < DSCR_MIN
    bad_loan = _loan_invalid(best)
    if low_dscr or bad_loan:
        if bad_loan:
            logger.warning("bank-loan pipeline: term_loan_amount is 0/missing despite "
                           "Bank Loan purpose — retrying assumptions once.")
        if low_dscr:
            logger.warning("bank-loan pipeline: DSCR %.2f < %.2f — retrying assumptions once",
                           best["dscr"], DSCR_MIN)
        try:
            retry = _attempt(purpose_key, industry, purpose, user_details)
            # An attempt with a real loan always beats one without, whatever the DSCRs
            # say — a 0/0 DSCR is not a score worth comparing. Only when both attempts
            # agree on loan validity does the higher DSCR decide.
            retry_bad_loan = _loan_invalid(retry)
            if bad_loan and not retry_bad_loan:
                best = retry
            elif retry_bad_loan and not bad_loan:
                pass  # keep the first attempt; the retry lost its loan
            else:
                best = _better(best, retry)
            logger.warning("bank-loan pipeline: retry DSCR %s; keeping %s (DSCR %s)",
                           f"{retry['dscr']:.2f}" if retry["dscr"] is not None else "unknown",
                           "retry" if best is retry else "first attempt",
                           f"{best['dscr']:.2f}" if best["dscr"] is not None else "unknown")
        except Exception as e:
            logger.warning("bank-loan pipeline: retry failed (%s); keeping first attempt", e)

    # Only the winning workbook is ever written, so generated_reports/ never holds a
    # discarded attempt.
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = _output_name(industry, purpose)
    report_path = os.path.join(REPORTS_DIR, filename)
    with open(report_path, "wb") as fh:
        fh.write(best["xlsx"])

    dscr = best["dscr"]
    # A model with no term loan can never be viable: its DSCR is 0/0, not a real score.
    final_bad_loan = _loan_invalid(best)
    viable = (dscr is not None and dscr >= DSCR_MIN) and not final_bad_loan
    ceiling_flag = dscr is not None and dscr > DSCR_CEILING
    diag = best["capacity_diag"]

    if final_bad_loan:
        logger.warning("bank-loan pipeline: term_loan_amount still 0/missing after retry "
                       "— returning the report with viable=False.")
    if ceiling_flag:
        logger.warning("bank-loan pipeline: DSCR %.1f exceeds ceiling %.1f — the loan may be "
                       "far too small for this business's revenue scale; review the "
                       "assumptions.", dscr, DSCR_CEILING)

    # A large scale-up means the AI described a business far smaller than the loan it
    # was told to service. The report is still returned — this is a review flag, not
    # an error — but it must be loud in the logs, not buried in the response body.
    if diag["flagged_implausible"]:
        logger.warning(
            "capacity guard: scaled capacity %.1fx (%s -> %s) — loan size may be too "
            "large for the stated business; review before accepting this report as-is.",
            diag["scaling_multiplier"], f"{diag['original_capacity']:,}",
            f"{diag['final_capacity']:,}")

    logger.info("bank-loan pipeline: %s/%s -> %s (%d cells, recalculated=%s, DSCR=%s, viable=%s)",
                industry, purpose, filename, best["filled"], best["recalculated"],
                f"{dscr:.2f}" if dscr is not None else "unknown", viable)

    return {
        "success": True,
        "report_path": report_path,
        "filename": filename,
        "assumptions": best["assumptions"],
        "recalculated": best["recalculated"],
        "cells_filled": best["filled"],
        "dscr_year1": dscr,
        "viable": viable,
        "dscr_ceiling_flag": ceiling_flag,
        "capacity_guard_fired": diag["capacity_guard_fired"],
        "capacity_scaling_multiplier": diag["scaling_multiplier"],
        "capacity_plausibility_flag": diag["flagged_implausible"],
    }
