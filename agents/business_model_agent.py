"""Section writers for the front of the report — the Business Model, and the Executive
Summary when the stored one is too short to fill its page.

Normally both come out of the single big model call along with the rest of the narrative.
These agents exist for the other case: a report generated before the section was part of
the report at all, or written so briefly it left half a page blank. Rather than force a
full regeneration — minutes of reasoning, and every figure recomputed — the one section is
written from the SAME stored figures the rest of the report already shows, and persisted
with the model.
"""
import logging

from services.claude_service import invoke_llm

logger = logging.getLogger(__name__)

_PROMPT = """You are a senior Chartered Accountant writing ONE section of a bank-grade
appraisal report: the Business Model.

Business: {title}
Industry: {industry}{sub}
Location: {location}, {country}
Target market: {target_market}
Description: {description}
Project cost: {project_cost}   Promoter contribution: {own_contribution}   Loan: {loan}
{figures}
Explain in full how THIS business makes money:
- what exactly is sold and to whom;
- the revenue streams and roughly what share each contributes;
- how it is priced, the channels used, and how customers are won and kept;
- the cost structure — what is fixed, what varies with volume;
- the working-capital cycle — who pays when, what stock is held, and for how long;
- the operating drivers the profit actually depends on;
- what makes the model defensible against the competition it faces.

Write about this business using its own numbers, not a textbook description of the
industry. Every figure you quote must be one of the figures given above — do not invent
any others, and do not contradict them. Reproduce them exactly as they are written above:
never expand a rounded figure into its raw decimals, and never write a ratio or a
percentage to more than two decimal places. 4-6 substantial paragraphs. Markdown: use "## " for
a sub-heading and "- " for a bullet. Do not write a heading for the section itself, do not
write a conclusion, and do not repeat the executive summary.
"""


_CARD_LABELS = {
    "revenue_y1": ("Year-1 revenue", "money"),
    "revenue_y5": ("Year-5 revenue", "money"),
    "ebitda_y5": ("Year-5 EBITDA", "money"),
    "pat_y5": ("Year-5 profit after tax", "money"),
    "avg_dscr": ("Average DSCR", "ratio"),
    "net_margin_y5": ("Year-5 net margin", "percent"),
}


def _money(v):
    """A stored amount, written the way the report writes it.

    The project cost, contribution and loan used to go into the prompt as bare integers,
    and came back out of the model the same way — "the total project cost is 4000000" in
    the middle of a bank submission.
    """
    try:
        v = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError, AttributeError):
        return "N/A"
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:,.2f} crore (₹{v:,.0f})"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:,.2f} lakh (₹{v:,.0f})"
    return f"₹{v:,.0f}"


def _figure_block(cards: dict) -> str:
    """The headline figures, written the way the report writes them.

    Handed over raw, the model quoted them raw — "revenue of ₹7,630,949.7318" and a net
    margin of "0.192117865313576" in the middle of a bank submission. Rounding here, in
    the shape the reader will see elsewhere in the report, is what stops that.
    """
    lines = []
    for key, (label, kind) in _CARD_LABELS.items():
        v = cards.get(key)
        if not isinstance(v, (int, float)):
            continue
        if kind == "money":
            v = float(v)
            if abs(v) >= 1e7:
                text = f"₹{v / 1e7:,.2f} crore (₹{v:,.0f})"
            elif abs(v) >= 1e5:
                text = f"₹{v / 1e5:,.2f} lakh (₹{v:,.0f})"
            else:
                text = f"₹{v:,.0f}"
        elif kind == "ratio":
            text = f"{v:.2f}x"
        else:
            text = f"{v * 100:.1f}%"
        lines.append(f"- {label}: {text}")
    if not lines:
        return ""
    return ("\nFIGURES FROM THE FINANCIAL MODEL — quote these EXACTLY as written here, "
            "rounded as shown, and quote no others:\n" + "\n".join(lines) + "\n")


def business_model_agent(project: dict, financial_summary: dict = None) -> str:
    """The section's markdown, or "" if it could not be written."""
    figures = _figure_block((financial_summary or {}).get("cards") or {})
    try:
        out = invoke_llm(_PROMPT.format(
            title=project.get("title") or "the business",
            industry=project.get("industry") or "N/A",
            sub=f" ({project['sub_industry']})" if project.get("sub_industry") else "",
            location=project.get("location") or "N/A",
            country=project.get("country") or "India",
            target_market=project.get("target_market") or "not stated",
            description=(project.get("description") or "")[:800],
            project_cost=_money(project.get("project_cost")),
            own_contribution=_money(project.get("own_contribution")),
            loan=_money(project.get("loan_amount")),
            figures=figures,
        ))
        return (out or "").strip()
    except Exception:
        logger.warning("business model: section unavailable", exc_info=True)
        return ""


# A page of this report holds roughly this much prose alongside the KPI card strip. Below
# the floor the summary is expanded; the target is what the expansion is asked for.
EXEC_MIN_WORDS = 350
EXEC_TARGET_WORDS = 500

_EXEC_PROMPT = """You are a senior Chartered Accountant writing the EXECUTIVE SUMMARY of a
bank-grade appraisal report. It must stand on its own: a credit officer who reads only this
page should understand the proposal and the case for it.

Business: {title}
Industry: {industry}{sub}
Location: {location}, {country}
Target market: {target_market}
Description: {description}
Project cost: {project_cost}   Promoter contribution: {own_contribution}   Loan sought: {loan}
{figures}
{existing}
Write a FULL PAGE — {target} words or more, in 5 to 7 substantial paragraphs. Cover, in this
order: what the business is and what it proposes to do; the promoter and their standing;
the market and demand it is addressing; the cost of the project and how it is funded; the
projected results and what they mean for viability; the coverage and comfort available to
the lender; and the risks with how they are managed.

Rules:
- Every figure you quote must be one of the figures given above. Quote no others, invent
  nothing, and contradict nothing.
- Reproduce figures exactly as written above — never expand a rounded figure into its raw
  decimals, and never write a ratio or percentage to more than two decimal places.
- Continuous professional prose. No headings, no bullet lists, no tables, no markdown.
- Do not write the words "Executive Summary" — the heading is added for you.
- Do not close with a "Conclusion" or a recommendation heading; the report has its own.
"""


def exec_summary_agent(project: dict, financial_summary: dict = None,
                       existing: str = "") -> str:
    """A full-page Executive Summary. "" if it could not be written.

    An existing summary is passed in and the model is told to keep every claim in it: this
    runs on reports that already have one, and the expansion must not quietly change what
    the report already told the client.
    """
    prior = (existing or "").strip()
    prior_block = (
        "The report already carries this summary. KEEP every fact and claim it makes, and "
        "expand it to the required length with the material below — do not contradict it "
        "and do not drop anything from it:\n\"\"\"\n" + prior + "\n\"\"\"\n"
    ) if prior else ""
    try:
        out = invoke_llm(_EXEC_PROMPT.format(
            title=project.get("title") or "the business",
            industry=project.get("industry") or "N/A",
            sub=f" ({project['sub_industry']})" if project.get("sub_industry") else "",
            location=project.get("location") or "N/A",
            country=project.get("country") or "India",
            target_market=project.get("target_market") or "not stated",
            description=(project.get("description") or "")[:800],
            project_cost=_money(project.get("project_cost")),
            own_contribution=_money(project.get("own_contribution")),
            loan=_money(project.get("loan_amount")),
            figures=_figure_block((financial_summary or {}).get("cards") or {}),
            existing=prior_block,
            target=EXEC_TARGET_WORDS,
        ))
        out = (out or "").strip()
        # A shorter result than what is already there is not an improvement.
        return out if len(out.split()) > len(prior.split()) else ""
    except Exception:
        logger.warning("executive summary: could not expand", exc_info=True)
        return ""
