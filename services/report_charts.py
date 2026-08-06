"""
report_charts.py

Renders the report's charts as PNG bytes (matplotlib, Agg) so they can be embedded
in the Word document. Every chart is driven by the SAME financial_summary that the
tables use, so the visuals and the numbers always agree.

House style: deep navy + gold on a clean white field, value labels on bars, muted
gridlines, no chart-junk — a bank/analyst look, not a spreadsheet default.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("report_charts")

# House palette taken from the client's reference report: periwinkle indigo on white,
# with a lighter tint for the second series and a near-black for labels.
NAVY = "#3B37D8"          # deep indigo — titles / value labels
NAVY_SOFT = "#5B5BF5"     # primary series
GOLD = "#8F8FF8"          # secondary series (lighter tint of the same hue)
GREEN = "#3FB08A"
RED = "#E2574C"
GREY = "#8A8FA3"
GRID = "#DFDFF2"
PRIMARY = "#5B5BF5"

_YEARS = ["Y1", "Y2", "Y3", "Y4", "Y5"]


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager  # noqa: F401
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.edgecolor": GREY,
        "axes.linewidth": 0.6,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "grid.linestyle": "--",
        "axes.axisbelow": True,
        "figure.dpi": 150,
    })
    return plt


def _clean(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)


def _scale(values):
    """Pick a ₹ unit (Cr / L) that reads cleanly for the largest value."""
    m = max((abs(v) for v in values if isinstance(v, (int, float))), default=0)
    if m >= 1e7:
        return 1e7, "₹ Cr"
    if m >= 1e5:
        return 1e5, "₹ Lakh"
    return 1.0, "₹"


def _save(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _series(summary, group, name):
    vals = ((summary.get(group) or {}).get(name)) or []
    return [v if isinstance(v, (int, float)) else 0 for v in vals][:5]


def revenue_profit_chart(summary) -> bytes | None:
    """Revenue bars with EBITDA and PAT trend lines — the headline growth story."""
    rev = _series(summary, "series", "Net Sales / Revenue")
    ebitda = _series(summary, "series", "EBITDA")
    pat = _series(summary, "series", "Profit After Tax")
    if not any(rev):
        return None
    try:
        plt = _mpl()
        div, unit = _scale(rev + ebitda + pat)
        rev_s = [v / div for v in rev]; eb_s = [v / div for v in ebitda]; pat_s = [v / div for v in pat]
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        x = range(5)
        bars = ax.bar(x, rev_s, width=0.56, color=PRIMARY, label="Revenue", zorder=3)
        for b, v in zip(bars, rev_s):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:,.1f}", ha="center", va="bottom",
                    fontsize=7.5, color=NAVY, fontweight="bold")
        if any(ebitda):
            ax.plot(x, eb_s, color=NAVY, marker="o", markersize=4, linewidth=2, label="EBITDA", zorder=4)
        if any(pat):
            ax.plot(x, pat_s, color=GREEN, marker="s", markersize=4, linewidth=2, label="PAT", zorder=4)
        ax.set_xticks(list(x)); ax.set_xticklabels(_YEARS)
        ax.set_ylabel(unit, fontsize=8, color=GREY)
        ax.legend(loc="upper left", frameon=False, fontsize=8, ncol=3)
        ax.margins(y=0.18)
        _clean(ax)
        return _save(fig)
    except Exception:
        logger.warning("revenue_profit_chart failed", exc_info=True)
        return None


def dscr_chart(summary) -> bytes | None:
    """DSCR by year with the 1.20 bank-floor threshold — green above, red below."""
    dscr = _series(summary, "ratios", "DSCR")
    if not any(dscr):
        return None
    try:
        plt = _mpl()
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        x = range(5)
        colors = [PRIMARY if v >= 1.2 else RED for v in dscr]
        bars = ax.bar(x, dscr, width=0.6, color=colors, zorder=3)
        for b, v in zip(bars, dscr):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom",
                    fontsize=7.5, color=NAVY, fontweight="bold")
        ax.axhline(1.2, color=RED, linestyle="--", linewidth=1, zorder=2)
        ax.text(-0.45, 1.2, "1.20 bank floor", fontsize=6.5, color=RED, ha="left", va="bottom")
        ax.set_xticks(list(x)); ax.set_xticklabels(_YEARS)
        ax.set_ylim(0, max(dscr) * 1.22)
        ax.set_title("Debt Service Coverage (DSCR)", fontsize=8.5, color=NAVY, fontweight="bold", pad=8)
        _clean(ax)
        return _save(fig)
    except Exception:
        logger.warning("dscr_chart failed", exc_info=True)
        return None


def segment_donut(segments) -> bytes | None:
    """Revenue mix by target-market segment as a donut — the share each part of the
    client's own market contributes."""
    rows = [s for s in (segments or []) if s.get("name") and isinstance(s.get("y1"), (int, float))
            and s["y1"] > 0]
    if len(rows) < 2:
        return None
    try:
        plt = _mpl()
        labels = [s["name"] for s in rows]
        values = [s["y1"] for s in rows]
        shades = [PRIMARY, "#8F8FF8", "#B9B9FB", "#6E6EE8", "#D2D2FD"]
        colors = [shades[i % len(shades)] for i in range(len(rows))]
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        wedges, _texts, autotexts = ax.pie(
            values, colors=colors, startangle=90, counterclock=False,
            autopct=lambda p: f"{p:.0f}%", pctdistance=0.78,
            wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2})
        for t in autotexts:
            t.set_color("white"); t.set_fontsize(8); t.set_fontweight("bold")
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
                  frameon=False, fontsize=8)
        ax.set_title("Revenue Mix by Target Market Segment", fontsize=9,
                     color=NAVY, fontweight="bold", pad=10)
        ax.axis("equal")
        ax.grid(False)
        return _save(fig)
    except Exception:
        logger.warning("segment_donut failed", exc_info=True)
        return None


def cost_structure_donut(summary) -> bytes | None:
    """Where each rupee of Year-1 revenue goes: cost of sales, operating costs and
    what is left as EBITDA."""
    rev = _series(summary, "series", "Net Sales / Revenue")
    eb = _series(summary, "series", "EBITDA")
    if not rev or not rev[0] or rev[0] <= 0:
        return None
    revenue = rev[0]
    ebitda = eb[0] if eb else 0
    costs = revenue - ebitda
    if costs <= 0:
        return None
    try:
        plt = _mpl()
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        labels = ["Operating costs", "EBITDA"]
        values = [costs, max(ebitda, 0)]
        colors = [PRIMARY, "#3FB08A" if ebitda > 0 else RED]
        wedges, _t, autotexts = ax.pie(
            values, colors=colors, startangle=90, counterclock=False,
            autopct=lambda p: f"{p:.0f}%", pctdistance=0.78,
            wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2})
        for t in autotexts:
            t.set_color("white"); t.set_fontsize(9); t.set_fontweight("bold")
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
                  frameon=False, fontsize=8)
        ax.set_title("Year-1 Revenue Split: Costs vs EBITDA", fontsize=9,
                     color=NAVY, fontweight="bold", pad=10)
        ax.axis("equal")
        ax.grid(False)
        return _save(fig)
    except Exception:
        logger.warning("cost_structure_donut failed", exc_info=True)
        return None


def margin_chart(summary) -> bytes | None:
    """EBITDA and net-profit margin trend."""
    eb = _series(summary, "ratios", "EBITDA Margin")
    npm = _series(summary, "ratios", "Net Profit Margin")
    if not any(eb) and not any(npm):
        return None
    try:
        plt = _mpl()
        fig, ax = plt.subplots(figsize=(6.0, 3.2))
        x = range(5)
        if any(eb):
            ax.plot(x, [v * 100 for v in eb], color=PRIMARY, marker="o", markersize=4, linewidth=2, label="EBITDA %")
        if any(npm):
            ax.plot(x, [v * 100 for v in npm], color=GOLD, marker="s", markersize=4, linewidth=2, label="Net Profit %")
        ax.set_xticks(list(x)); ax.set_xticklabels(_YEARS)
        ax.set_ylabel("% of sales", fontsize=8, color=GREY)
        ax.set_title("Profitability Margins", fontsize=8.5, color=NAVY, fontweight="bold", pad=8)
        ax.legend(loc="upper left", frameon=False, fontsize=7.5)
        ax.margins(y=0.25)
        _clean(ax)
        return _save(fig)
    except Exception:
        logger.warning("margin_chart failed", exc_info=True)
        return None
