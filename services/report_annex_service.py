"""
report_annex_service.py

Builds the narrative content for the workbook's two annex sheets — SWOT and
Conclusion — as ordinary "Sheet!Cell" -> text answers, so the existing template-fill
mechanism writes them with everything else (no new write path).

The SWOT quadrants come from the same swot_agent that feeds the Word report; here we
parse its four sections into the four quadrant cells. The Conclusion narrative is
synthesised from the model's own figures (revenue trajectory, DSCR, profitability),
so it never quotes a number the Excel disagrees with and needs no extra LLM call.

These cells target the bank_loan CMA workbook's SWOT / Conclusion sheets. For any
template that does not have those sheets the keys simply find no sheet and are
skipped by fill_template — safe to always include.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("report_annex")

# Cell map — must match the sheets added to CMA_Dashboard_Premium.xlsx.
SWOT_CELLS = {
    "strengths": "SWOT!B6",
    "weaknesses": "SWOT!D6",
    "opportunities": "SWOT!B8",
    "threats": "SWOT!D8",
}
CONCLUSION_CELL = "Conclusion!B28"

_SECTIONS = ("strengths", "weaknesses", "opportunities", "threats")


def _parse_swot(md: str) -> dict:
    """Split swot_agent markdown into four bullet blocks. Tolerant of '### Strengths',
    '**Strengths**', 'Strengths:' and of '-', '*' or numbered bullets."""
    out = {k: [] for k in _SECTIONS}
    if not md:
        return out
    current = None
    for raw in md.splitlines():
        line = raw.strip()
        low = re.sub(r"[^a-z]", "", line.lower())
        matched = None
        for sec in _SECTIONS:
            # a heading line that is essentially just the section word
            if low.startswith(sec) and len(low) <= len(sec) + 2:
                matched = sec
                break
        if matched:
            current = matched
            continue
        if current and line:
            item = re.sub(r"^[-*•\d.)\s]+", "", line).strip()
            # skip markdown table rows / separators
            if item and not item.startswith("|") and not set(item) <= set("-|: "):
                out[current].append(item)
    return out


def _bullets(items: list, limit: int = 6) -> str:
    """Quadrant text: up to `limit` concise bullet lines."""
    picked = [i for i in items if i][:limit]
    return "\n".join(f"•  {i}" for i in picked)


def _fmt_inr(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a >= 1e7:
        return f"₹{v/1e7:,.2f} Cr"
    if a >= 1e5:
        return f"₹{v/1e5:,.2f} L"
    return f"₹{v:,.0f}"


def _conclusion_text(project, kpis: dict) -> str:
    """A professional, data-grounded conclusion paragraph built from the model's own
    figures. kpis: optional {'revenue_y1','revenue_y5','pat_y5','avg_dscr','irr',...}."""
    name = getattr(project, "title", None) or "The project"
    industry = getattr(project, "industry", None) or "the sector"
    parts = []
    parts.append(
        f"{name} has been appraised as a {industry} venture over a five-year projection "
        f"horizon on the basis of the assumptions and financial statements in this workbook."
    )

    rev1, rev5 = kpis.get("revenue_y1"), kpis.get("revenue_y5")
    if rev1 and rev5:
        try:
            growth = (float(rev5) / float(rev1) - 1) * 100 if float(rev1) else 0
            parts.append(
                f"Revenue is projected to grow from {_fmt_inr(rev1)} in Year 1 to "
                f"{_fmt_inr(rev5)} by Year 5 ({growth:+.0f}% over the period), reflecting the "
                f"capacity build-up and demand assumptions adopted."
            )
        except (TypeError, ValueError):
            pass

    dscr = kpis.get("avg_dscr")
    if dscr is not None:
        try:
            d = float(dscr)
            if d >= 1.5:
                verdict = ("comfortably serviceable, with the average DSCR well above the "
                           "1.20 benchmark banks look for")
            elif d >= 1.2:
                verdict = ("serviceable, with the average DSCR meeting the 1.20 minimum "
                           "banks look for")
            else:
                verdict = ("below the 1.20 DSCR benchmark banks look for, indicating the "
                           "debt structure or margins should be revisited before sanction")
            parts.append(f"The debt is {verdict} (average DSCR {d:.2f}).")
        except (TypeError, ValueError):
            pass

    pat5 = kpis.get("pat_y5")
    if pat5 is not None:
        try:
            p = float(pat5)
            if p > 0:
                parts.append(
                    f"The project turns a Year-5 profit after tax of {_fmt_inr(p)}, and the "
                    f"cash accruals support the projected repayment schedule."
                )
            else:
                parts.append(
                    "The project does not reach a positive Year-5 profit after tax on the "
                    "current assumptions; pricing, cost or scale assumptions warrant review."
                )
        except (TypeError, ValueError):
            pass

    parts.append(
        "On the strength of the projected financials, ratios and coverage set out above, "
        "the proposal is considered financially viable, subject to the assumptions holding "
        "and the usual terms of sanction."
    )
    return "  ".join(parts)


def _kpis_from_model(model: dict) -> dict:
    """Pull the handful of figures the conclusion needs out of the stored model, if
    present. Best-effort — any missing field simply drops its sentence."""
    k = {}
    if not isinstance(model, dict):
        return k
    fm = model.get("financials") or model.get("engine") or model
    # common shapes: annual lists under 'revenue'/'pat', or a ratios block
    def _first_last(seq):
        if isinstance(seq, (list, tuple)) and seq:
            return seq[0], seq[-1]
        return None, None
    rev = (fm.get("revenue") or fm.get("annual_revenue")
           or (fm.get("profit") or {}).get("revenue"))
    r1, r5 = _first_last(rev)
    k["revenue_y1"], k["revenue_y5"] = r1, r5
    pat = (fm.get("pat") or (fm.get("profit") or {}).get("pat"))
    _, p5 = _first_last(pat)
    k["pat_y5"] = p5
    ratios = fm.get("ratios") or {}
    k["avg_dscr"] = ratios.get("average_dscr") or model.get("avg_dscr")
    return {kk: vv for kk, vv in k.items() if vv is not None}


def build_annex_cell_answers(project, purpose_label: str = "", model: dict = None,
                             swot_markdown: str = None) -> dict:
    """Return {"SWOT!B6": ..., ..., "Conclusion!B28": ...} for the workbook annex.

    swot_markdown: pass the swot_agent output if already computed; else it is
    generated here. Failures are non-fatal — a missing quadrant just stays blank."""
    answers = {}

    # SWOT
    try:
        md = swot_markdown
        if md is None:
            from agents.swot_agent import swot_agent
            md = swot_agent(
                business_name=getattr(project, "title", "") or "",
                industry=getattr(project, "industry", "") or "",
                country=getattr(project, "country", "") or "",
                description=getattr(project, "project_description", "") or "",
            )
        quad = _parse_swot(md)
        for sec, cell in SWOT_CELLS.items():
            text = _bullets(quad.get(sec, []))
            if text:
                answers[cell] = text
    except Exception:
        logger.warning("annex: SWOT build failed", exc_info=True)

    # Conclusion
    try:
        answers[CONCLUSION_CELL] = _conclusion_text(project, _kpis_from_model(model or {}))
    except Exception:
        logger.warning("annex: conclusion build failed", exc_info=True)

    return answers
