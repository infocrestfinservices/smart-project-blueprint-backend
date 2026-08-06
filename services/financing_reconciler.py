"""
financing_reconciler.py

Makes the workbook's money tie to what the CLIENT actually said.

The AI fills the financing cells (term loan, promoter's capital) from the client's
stated figures, but it filled the COST-OF-PROJECT components (land, building, plant &
machinery, furniture) independently — so a project the client costed at ₹3 crore, and
financed with a ₹2.1 crore loan, showed only ₹40 lakh of assets being bought. Sources
did not equal uses, and the first question any CA or banker asks is "where did the rest
of the money go?".

This runs AFTER the AI fill and BEFORE the workbook is filled, and enforces
deterministically (never by asking the model again):

  1. Term loan and promoter's capital are the client's stated numbers, full stop.
  2. The cost-of-project components are scaled proportionally so they add up to the
     cost of project — which, in the CMA convention this workbook follows, is what the
     term loan plus promoter's capital funds. (Working capital is financed separately
     by the WC limit the model computes in Form V, so it is deliberately not part of
     this total.)
  3. If the AI gave no usable breakdown at all, a conventional split is applied so the
     total still ties instead of leaving the assets blank.

Only the CMA-family workbooks use these cells; a template without them is left alone.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("financing_reconciler")

# Cost-of-project cells in the CMA family, with the fallback share of the total used
# only when the AI produced no usable breakdown.
_ASSET_CELLS = [
    ("Assumptions!C42", "land", 0.00),
    ("Assumptions!C43", "building", 0.35),
    ("Assumptions!C45", "plant & machinery / equipment", 0.45),
    ("Assumptions!C47", "furniture & other", 0.20),
]
_LOAN_CELL = "Assumptions!C8"
_EQUITY_CELL = "Assumptions!C9"
_TENURE_CELL = "Assumptions!C11"       # MONTHS
_MORATORIUM_CELL = "Assumptions!C12"   # MONTHS


def _fix_months(out: dict):
    """The tenure and moratorium cells are in MONTHS. The label used to say only
    "Term Loan tenure", so the AI filled 5 — meaning 5 years — and the model repaid a
    ₹35 lakh loan in five months: the term loan vanished from the balance sheet by
    Year 1, cash went ₹25 lakh negative and DSCR collapsed to zero. Anything under a
    year is therefore read as years and converted."""
    t = _num(out.get(_TENURE_CELL))
    if t is not None and 0 < t < 12:
        out[_TENURE_CELL] = int(round(t * 12))
        logger.info("financing: term-loan tenure %.0f looked like YEARS; using %d months",
                    t, out[_TENURE_CELL])
    m = _num(out.get(_MORATORIUM_CELL))
    if m is not None and 0 < m < 4 and (out.get(_TENURE_CELL) or 0) >= 12:
        # a 1-3 "month" moratorium alongside a multi-year loan is usually years too,
        # but this one is genuinely ambiguous — leave it, only clamp the absurd case.
        pass
    if m is not None and m < 0:
        out[_MORATORIUM_CELL] = 0


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def reconcile_financing(answers: dict, project) -> dict:
    """Return `answers` with the financing and cost-of-project cells made consistent
    with the client's stated figures. Mutates nothing the caller owns."""
    if not isinstance(answers, dict) or not answers:
        return answers
    # Only applies to workbooks that actually carry these cells.
    if not any(c in answers for c, _, _ in _ASSET_CELLS) and _LOAN_CELL not in answers:
        return answers

    out = dict(answers)
    loan = _num(getattr(project, "loan_amount", None))
    equity = _num(getattr(project, "own_contribution", None))
    stated_cost = _num(getattr(project, "project_cost", None))

    # 1. the client's own financing figures win
    if loan is not None:
        out[_LOAN_CELL] = loan
    if equity is not None:
        out[_EQUITY_CELL] = equity

    # 1b. repayment period is in months — a years-shaped value destroys the model
    _fix_months(out)

    # 2. what the project has to fund: prefer the stated cost, else what is financed
    funded = None
    if loan is not None or equity is not None:
        funded = (loan or 0) + (equity or 0)
    target = stated_cost if stated_cost else funded
    if not target or target <= 0:
        return out

    current = {c: (_num(out.get(c)) or 0.0) for c, _, _ in _ASSET_CELLS}
    total = sum(current.values())

    if total > 0:
        factor = target / total
        # Leave it alone when it already ties (within 2%) — no need to touch a
        # breakdown the AI got right.
        if abs(factor - 1.0) <= 0.02:
            return out
        for cell, _label, _share in _ASSET_CELLS:
            out[cell] = round(current[cell] * factor, 2)
        logger.info("financing: scaled cost of project %.0f -> %.0f (x%.2f) to match "
                    "the stated project cost", total, target, factor)
    else:
        # 3. nothing usable from the AI — apply a conventional split so the total ties
        for cell, _label, share in _ASSET_CELLS:
            out[cell] = round(target * share, 2)
        logger.info("financing: no asset breakdown from the AI; applied a conventional "
                    "split over %.0f", target)

    return out


# Fixed-asset intensity by operating-model family/key: the share of the cost of project
# that a business of this kind actually sinks into FIXED assets. Capital-light service
# industries spend only a fraction on assets; the rest is working capital / cash. The AI
# (and reconcile_financing after it) puts 100% into fixed assets, which leaves ZERO cash
# cushion, so a ramp-year loss drives the balance-sheet cash figure negative and every
# liquidity ratio with it. This only ever REDUCES fixed assets — never inflates them.
_CAPEX_FIXED_ASSET_SHARE = {
    "trading": 0.15, "software": 0.20, "media": 0.20, "education": 0.25,
    "retail": 0.30, "other": 0.30, "restaurant": 0.45, "transport": 0.55,
    "hospital": 0.60, "hotel": 0.65,
}


_WC_DAY_CELLS = {
    "Assumptions!C50": 30,   # raw-material holding
    "Assumptions!C51": 15,   # finished-goods holding
    "Assumptions!C52": 45,   # debtors / receivables
    "Assumptions!C53": 30,   # creditors / payables
}
_GROWTH_Y1_CELL = "Assumptions!C18"
_GROSS_MARGIN_CELL = "Assumptions!C25"


def reconcile_working_capital(answers: dict, project) -> dict:
    """Clamp AI-filled working-capital inputs that come back with absurd units/scale.

    Seen in the wild: the AI put a debtor-days of 2,000,000 (should be ~45) and a
    creditor-days of 800,000, which blew receivables up to ₹41 billion, the working-capital
    borrowing and its interest with it, and turned every ratio astronomically negative
    (Net Profit −14,000,000 %, DSCR −6 lakh×). Nothing guarded these cells.

    Only acts on values that are clearly out of range, so every sane figure — including all
    Bank Loan / manufacturing values — is left exactly as it is.
    """
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)

    # 1. Holding-period days — nothing in this model legitimately exceeds a year.
    for cell, default in _WC_DAY_CELLS.items():
        v = _num(out.get(cell))
        if v is not None and v > 365:
            logger.info("working-capital: %s = %s days is absurd; using %d", cell, v, default)
            out[cell] = default

    # 2. Year-1 growth index is the base year: it must be ~1.0. A value like 0.1875 scales
    #    the whole first year to a fraction of itself.
    g = _num(out.get(_GROWTH_Y1_CELL))
    if g is not None and not (0.5 <= g <= 1.5):
        logger.info("working-capital: Year-1 growth index %s reset to 1.0 (base year)", g)
        out[_GROWTH_Y1_CELL] = 1.0

    # 3. Gross margin is a 0-1 fraction — but ONLY for the volume-price family; for the
    #    capacity family C25 is a per-unit raw-material cost and must never be touched.
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        fam = getattr(get_operating_model(getattr(project, "industry", "") or ""), "family", "")
    except Exception:
        fam = ""
    if fam == "volume_price":
        m = _num(out.get(_GROSS_MARGIN_CELL))
        if m is not None and not (0 < m <= 1):
            fixed = m / 100 if 1 < m <= 100 else 0.6   # 60 -> 0.60; anything wilder -> default
            if not (0 < fixed <= 1):
                fixed = 0.6
            logger.info("working-capital: gross margin %s -> %s (must be a 0-1 fraction)", m, fixed)
            out[_GROSS_MARGIN_CELL] = round(fixed, 4)

    return out


def reconcile_capex(answers: dict, project) -> dict:
    """Stop 100% of the cost of project being sunk into fixed assets for capital-light
    industries, so there is a working-capital / cash cushion to absorb the ramp years.

    Deterministic and contained: it only rescales the four cost-of-project cells DOWN to a
    per-industry fixed-asset share and keeps the AI's proportional mix between them; the
    freed amount becomes the balance sheet's cash. Sources still equal uses (loan+equity
    fund fixed assets PLUS the cash margin). Runs AFTER reconcile_financing (which is what
    scales the assets up to 100%), and only for the volume_price family — the capacity
    family (manufacturing/textile/auto/mining → the frozen Bank Loan base) is never touched.
    """
    if not isinstance(answers, dict):
        return answers
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        m = get_operating_model(getattr(project, "industry", "") or "")
    except Exception:
        m = None
    if not m or getattr(m, "family", "") != "volume_price":
        return answers
    share = _CAPEX_FIXED_ASSET_SHARE.get(getattr(m, "key", ""), 0.30)

    loan = _num(getattr(project, "loan_amount", None)) or 0.0
    equity = _num(getattr(project, "own_contribution", None)) or 0.0
    total = _num(getattr(project, "project_cost", None)) or (loan + equity)
    if not total or total <= 0:
        return answers

    out = dict(answers)
    current = {c: (_num(out.get(c)) or 0.0) for c, _, _ in _ASSET_CELLS}
    fa_now = sum(current.values())
    fa_target = round(total * share, 2)
    # Only step in when the assets are heavier than the target (they will be — financing
    # scaled them to 100%). Keep the AI's split between the cells; just shrink the whole.
    if fa_now <= fa_target or fa_now <= 0:
        return out
    factor = fa_target / fa_now
    for cell, _label, _s in _ASSET_CELLS:
        out[cell] = round(current[cell] * factor, 2)
    logger.info("capex: fixed assets %.0f -> %.0f (%.0f%% of project) for key=%r; "
                "the %.0f freed becomes the cash/WC cushion",
                fa_now, fa_target, share * 100, getattr(m, "key", ""), fa_now - fa_target)
    return out


_NAME_CELL = "Assumptions!C5"
_CONSTITUTION_CELL = "Assumptions!C6"
_ACTIVITY_CELL = "Assumptions!C7"


def reconcile_identity(answers: dict, project) -> dict:
    """Force the business's identity onto the workbook from the PROJECT record.

    Who the borrower is is not the AI's to decide, but it was filling these cells like
    any other: regenerating a report quietly renamed the unit and rewrote its line of
    activity. The project is the authority — the AI's value is only a fallback for a
    field the user never gave."""
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    for cell, value in ((_NAME_CELL, getattr(project, "title", None)),
                        (_ACTIVITY_CELL, getattr(project, "project_description", None))):
        if isinstance(value, str) and value.strip():
            v = value.strip()
            if cell == _ACTIVITY_CELL and len(v) > 90:      # keep the cell readable
                v = v[:87].rsplit(" ", 1)[0] + "…"
            if out.get(cell) != v:
                logger.info("identity: %s %r -> %r", cell, out.get(cell), v)
                out[cell] = v
    # The promoter's own name belongs on the cover, not in the unit-name cell; a blank
    # constitution is left to the AI rather than invented here.
    return out


_INDUSTRY_CELL = "Assumptions!J5"


def reconcile_industry(answers: dict, project) -> dict:
    """Set the workbook's industry selector from the PROJECT's industry.

    Every industry-driven label in the workbook is a VLOOKUP on this one cell, and the
    AI was choosing it from the dropdown itself: a banana-chips plant whose industry is
    "Food Processing" got tagged as Food & Beverage / Restaurant, so the whole model
    was relabelled with "covers served" and "cost per cover". The project's own
    industry is the authority, so resolve it and write it in."""
    if not isinstance(answers, dict):
        return answers
    industry = getattr(project, "industry", None)
    if not industry:
        return answers
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        m = get_operating_model(industry)
    except Exception:
        m = None
    if not m:
        return answers
    out = dict(answers)
    if out.get(_INDUSTRY_CELL) != m.display_name:
        logger.info("industry: workbook selector %r -> %r (from project industry %r)",
                    out.get(_INDUSTRY_CELL), m.display_name, industry)
        out[_INDUSTRY_CELL] = m.display_name
    return out


_CAPACITY = "Assumptions!C16"
_UTIL_Y1 = "Assumptions!C18"
_PRICE = "Assumptions!C23"
_UNIT_COSTS = ("Assumptions!C25", "Assumptions!C27", "Assumptions!C29")
_MONTHLY_FIXED = ("Assumptions!C32", "Assumptions!C34", "Assumptions!C36", "Assumptions!C38")
_SELLING_PCT = "Assumptions!C40"


def reconcile_scale(answers: dict) -> dict:
    """Size the operation so the business is actually viable.

    The capacity cell is an ANNUAL volume, but the label carries no period, so the AI
    fills a daily or monthly figure: a ₹1 crore banana-chips plant came back with a
    capacity of 500 units A YEAR — ₹42,000 of revenue against ₹14.4 lakh of fixed
    costs, i.e. a guaranteed loss and the upside-down charts that go with it.

    Rather than trust the prompt, solve for the volume that makes the unit economics
    work. Holding price and per-unit costs (the AI's judgement about the market), the
    capacity that yields a 20% EBITDA margin is:

        capacity = annual fixed costs / (utilisation × (price×(0.8 − selling%) − unit cost))

    Only applied when the model as filled is NOT viable, and never scaled down."""
    if not isinstance(answers, dict) or _CAPACITY not in answers:
        return answers
    out = dict(answers)
    cap = _num(out.get(_CAPACITY))
    util = _num(out.get(_UTIL_Y1)) or 1.0
    price = _num(out.get(_PRICE))
    if not cap or not price or cap <= 0 or price <= 0 or util <= 0:
        return out

    unit_cost = sum(_num(out.get(c)) or 0.0 for c in _UNIT_COSTS)
    fixed = 12.0 * sum(_num(out.get(c)) or 0.0 for c in _MONTHLY_FIXED)
    sd = _num(out.get(_SELLING_PCT)) or 0.0

    units = cap * util
    revenue = units * price
    ebitda = revenue - units * unit_cost - fixed - revenue * sd
    if revenue > 0 and ebitda / revenue >= 0.08:
        return out                                    # already viable — leave it alone

    contribution = price * (0.8 - sd) - unit_cost     # per unit, after a 20% margin
    if contribution <= 0 or fixed <= 0:
        logger.warning("scale: unit economics unworkable (price %.2f vs unit cost %.2f); "
                       "capacity left as filled", price, unit_cost)
        return out

    needed = fixed / (util * contribution)
    if needed > cap:
        out[_CAPACITY] = round(needed, 2)
        logger.info("scale: capacity %.0f gave EBITDA %.0f on revenue %.0f (not viable); "
                    "raised to %.0f for a ~20%% margin", cap, ebitda, revenue, needed)
    return out


_STREAM_VOL_CELLS = ("Assumptions!C66", "Assumptions!C67",
                     "Assumptions!C68", "Assumptions!C69")
_STREAM_PRICE_CELLS = ("Assumptions!D66", "Assumptions!D67",
                       "Assumptions!D68", "Assumptions!D69")
# An ancillary block larger than this multiple of core revenue is not a business with
# side income, it is a mis-filled cell (a stray annual figure typed into a monthly box).
_STREAM_SANITY_CAP = 1.0
# A stream volume this many times larger than the industry expects is not a volume at
# all — it is the annual RUPEE amount from the pre-build-up format sitting in the cell.
_LEGACY_VOLUME_MULTIPLE = 20.0


def reconcile_streams(answers: dict, project) -> dict:
    """Make the "Additional revenue streams" block real for every industry.

    The industry templates model ancillary income (a hotel's F&B and banquets, a
    hospital's pharmacy and diagnostics, a SaaS firm's onboarding and AMC) as a real
    volume x price build-up: C66:C69 hold each stream's VOLUME and D66:D69 its PRICE.
    The Revenue Build-Up sheet multiplies them out, and Net Sales, the P&L and every
    downstream form read that total. Nothing forced the AI to fill those cells, so on
    most industries they came back 0 and every report shipped with an empty streams
    block and understated revenue — a hotel showing only room income reads as an
    incomplete projection to a banker.

    This is the deterministic guard, run post-AI exactly like reconcile_capex/_scale:

      1. Blank block -> seed each stream from the industry's own profile. The VOLUME
         comes from stream_vol_per_core (2.5 covers of F&B per room-night, 0.5
         diagnostic tests per patient), and the PRICE is then solved so the stream's
         revenue lands exactly on stream_mix x core revenue. Both drivers are therefore
         industry-shaped AND the revenue stays on the benchmark.
      2. Absurd block (streams exceeding core revenue) -> scale the PRICES back to the
         industry profile instead of letting one bad cell inflate Net Sales.
      3. Anything the AI or the user filled sensibly is LEFT ALONE.

    Scoped to the volume_price family. The capacity family (manufacturing/textile/auto/
    mining -> the frozen Bank Loan workbook) has no streams section and is never touched.
    """
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        m = get_operating_model(getattr(project, "industry", "") or "")
    except Exception:
        return out
    # Gated on the industry HAVING a stream profile rather than on its family: the
    # manufacturing workbook now carries ancillary output too (scrap, job work, trading),
    # so the capacity family is no longer excluded by definition. An industry with no
    # profile still gets nothing written.
    if not m:
        return out
    mix = getattr(m, "stream_mix", None) or (0.0, 0.0, 0.0, 0.0)
    vpc = getattr(m, "stream_vol_per_core", None) or (0.0, 0.0, 0.0, 0.0)
    if not any(mix) or not any(vpc):
        return out

    volume = _num(out.get(_CAPACITY)) or 0.0
    price = _num(out.get(_PRICE)) or 0.0
    core = volume * price
    if core <= 0 or volume <= 0:
        # No usable core revenue yet — seeding off it would be meaningless.
        return out

    def stream_revenue():
        return sum((_num(out.get(v)) or 0.0) * (_num(out.get(p)) or 0.0)
                   for v, p in zip(_STREAM_VOL_CELLS, _STREAM_PRICE_CELLS))

    # Repair stream by stream. An all-or-nothing test is not enough: a project created
    # before the volume x price build-up existed keeps its old ANNUAL AMOUNT in C, and
    # once the AI later fills a price into D that pair multiplies out to nonsense
    # (70,000,000 "covers" x Rs 0.04). Each stream is therefore judged on its own.
    fixed = []
    for i, (vcell, pcell) in enumerate(zip(_STREAM_VOL_CELLS, _STREAM_PRICE_CELLS)):
        want_vol = round(volume * vpc[i])
        v = _num(out.get(vcell)) or 0.0
        p = _num(out.get(pcell)) or 0.0
        if want_vol <= 0:
            continue
        if v > want_vol * _LEGACY_VOLUME_MULTIPLE:
            # C is money, not units — the pre-build-up format. Keep the FIGURE the
            # client agreed and re-express it as this industry's volume x price.
            target, why = v, "legacy amount"
        elif v <= 0 or p <= 0:
            # Never ship an empty stream — that was the original complaint.
            target, why = core * mix[i], "empty"
        else:
            continue                                    # sensible: leave it alone
        out[vcell] = want_vol
        out[pcell] = round(target / want_vol, 2)
        fixed.append(f"{i + 1}:{why}")
    if fixed:
        logger.info("streams: %s repaired %s; block now %.0f (core %.0f)",
                    m.display_name, ", ".join(fixed), stream_revenue(), core)

    total = stream_revenue()
    if total > core * _STREAM_SANITY_CAP:
        factor = (core * sum(mix)) / total
        for pcell in _STREAM_PRICE_CELLS:
            out[pcell] = round((_num(out.get(pcell)) or 0.0) * factor, 2)
        logger.info("streams: %s block %.0f exceeded core revenue %.0f; prices scaled "
                    "to give %.0f", m.display_name, total, core, stream_revenue())
    return out


_EXIST_TREATMENT = "Assumptions!C72"     # 1 = take-over, 2 = additional
_EXIST_OUTSTANDING = "Assumptions!C73"
_EXIST_RATE = "Assumptions!C74"
_EXIST_TENURE = "Assumptions!C75"        # MONTHS


def _yes(v) -> bool:
    return str(v or "").strip().lower()[:1] in ("y", "h", "1", "t")   # yes / haan / 1 / true


def _apply_loan_questionnaire(out: dict) -> dict:
    """Carry the questionnaire's plain-language answers into the cells.

    The five questions are free text or numbers, so "Take-over", "takeover", "take over"
    and "1" must all mean the same thing. Doing this here rather than leaving it to the
    AI means what the client SAID is what the workbook models.
    """
    asked = out.get("has_existing_loan")
    if asked is not None and not _yes(asked):
        out[_EXIST_OUTSTANDING] = 0            # answered "No" — nothing to model
        return out

    amt = _num(out.get("existing_loan_outstanding"))
    if amt is None:
        amt = _num(out.get("existing_borrowings"))     # the older single-number question
    if amt is not None and _num(out.get(_EXIST_OUTSTANDING)) in (None, 0):
        out[_EXIST_OUTSTANDING] = amt

    treat = out.get("existing_loan_treatment")
    if treat is not None and str(treat).strip():
        t = str(treat).strip().lower()
        if "take" in t or t.startswith("1") or "shift" in t:
            out[_EXIST_TREATMENT] = 1
        elif "add" in t or t.startswith("2") or "along" in t or "running" in t:
            out[_EXIST_TREATMENT] = 2

    rate = _num(out.get("existing_loan_rate"))
    if rate is not None and _num(out.get(_EXIST_RATE)) in (None, 0):
        out[_EXIST_RATE] = rate
    ten = _num(out.get("existing_loan_tenure_months"))
    if ten is not None and _num(out.get(_EXIST_TENURE)) in (None, 0):
        out[_EXIST_TENURE] = ten
    return out


def reconcile_existing_loan(answers: dict, project) -> dict:
    """Make the prior-debt inputs usable, or switch them off cleanly.

    Four cells describe a loan the borrower already has. Left half-filled they would
    quietly distort DSCR and debt-equity — an outstanding with no rate charges no
    interest; a rate entered as 11 instead of 0.11 charges eleven hundred percent; a
    tenure of 5 (meaning years) repays the whole facility in five months.

    With no outstanding the block is zeroed so every downstream formula reads 0 and the
    report looks exactly as it did before this feature existed.
    """
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    out = _apply_loan_questionnaire(out)
    amt = _num(out.get(_EXIST_OUTSTANDING)) or 0.0
    if amt <= 0:
        for c in (_EXIST_TREATMENT, _EXIST_OUTSTANDING, _EXIST_RATE, _EXIST_TENURE):
            out[c] = 0
        return out

    treat = _num(out.get(_EXIST_TREATMENT))
    if treat not in (1.0, 2.0):
        # "Additional" is the conservative reading: it keeps the obligation in DSCR
        # rather than assuming a take-over that may never be sanctioned.
        out[_EXIST_TREATMENT] = 2
        logger.info("existing loan: treatment %r not 1 or 2; defaulting to additional",
                    treat)

    rate = _num(out.get(_EXIST_RATE)) or 0.0
    if rate > 1:                       # entered as 11 rather than 0.11
        out[_EXIST_RATE] = round(rate / 100.0, 4)
        logger.info("existing loan: rate %.2f read as a percentage -> %.4f",
                    rate, out[_EXIST_RATE])
    elif rate <= 0:
        out[_EXIST_RATE] = _num(out.get("Assumptions!C10")) or 0.11
        logger.info("existing loan: no rate given; using the term-loan rate")

    ten = _num(out.get(_EXIST_TENURE)) or 0.0
    if 0 < ten < 12:                   # 5 meaning five YEARS
        out[_EXIST_TENURE] = int(round(ten * 12))
        logger.info("existing loan: tenure %.0f looked like YEARS; using %d months",
                    ten, out[_EXIST_TENURE])
    elif ten <= 0:
        out[_EXIST_TENURE] = 60
        logger.info("existing loan: no tenure given; assuming 60 months")
    return out


_GROWTH_CELLS = [f"Assumptions!{c}18" for c in "CDEFG"]
_PHASING_CELLS = [f"Assumptions!{c}21" for c in "CDEFGHIJKLMN"]
# Year 1..5. For the capacity family C18:G18 is capacity UTILISATION (a ramp up to full
# use); for volume_price it is a growth INDEX with Year 1 = 1.00.
_DEFAULT_UTILISATION = (0.60, 0.70, 0.80, 0.85, 0.90)
_DEFAULT_GROWTH_INDEX = (1.00, 1.10, 1.21, 1.33, 1.46)


def reconcile_drivers(answers: dict, project) -> dict:
    """Guarantee the year and month driver cells are numbers.

    C18:G18 (utilisation / growth index) and C21:N21 (monthly phasing) sit underneath
    every projected figure. Projects created before those cells were in the schema have
    them EMPTY, and the whole workbook then evaluates to #VALUE! — one real project came
    out with 536 broken cells across thirteen sheets, which is an unusable report rather
    than a wrong one. Missing or non-numeric entries are filled with a conventional ramp;
    anything already numeric is left exactly as it is.
    """
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    try:
        from financial_engine.industry_calc.operating_models import family_of
        capacity = family_of(getattr(project, "industry", "") or "") != "volume_price"
    except Exception:
        capacity = True
    ramp = _DEFAULT_UTILISATION if capacity else _DEFAULT_GROWTH_INDEX

    missing = [c for c in _GROWTH_CELLS if _num(out.get(c)) is None]
    if missing:
        for cell, val in zip(_GROWTH_CELLS, ramp):
            if _num(out.get(cell)) is None:
                out[cell] = val
        logger.info("drivers: %d of 5 year cells were not numeric; filled a %s ramp",
                    len(missing), "utilisation" if capacity else "growth")
    blank = [c for c in _PHASING_CELLS if _num(out.get(c)) is None]
    if blank:
        for cell in blank:
            out[cell] = 1.0
        logger.info("drivers: %d of 12 monthly phasing weights were blank; set to 1.0",
                    len(blank))
    return out


_WAGES_CELL = "Assumptions!C32"          # direct wages & salaries, per MONTH
_GM_CELL = "Assumptions!C25"             # gross margin (volume_price family)
_OTHER_FIXED = ("Assumptions!C34", "Assumptions!C36", "Assumptions!C38")
_SELLING_CELL = "Assumptions!C40"
# Never let the labour correction drive the business under. Raising wages to the
# industry band is right; raising them until the project cannot service its loan is not
# — that is how the "every capital-light report comes out negative" episode happened.
_MIN_EBITDA_MARGIN = 0.10


def reconcile_operating_costs(answers: dict, project) -> dict:
    """Peg direct wages to what the industry actually spends on people.

    Nothing in the pipeline ever compared a PERIOD cost against revenue. `reconcile_scale`
    sizes the VOLUME for viability, but the wage cell was whatever the AI typed, so real
    projects landed anywhere from 1.5% of revenue (a retail chain with no shop staff) to
    54%. The revenue streams made it worse: they add income but no incremental people, so
    every industry's EBITDA margin rose 1-6pp and labour's share fell.

    Both are fixed by measuring wages against TOTAL revenue — core plus streams — and
    clamping into the industry's own band. Running after reconcile_streams is what makes
    the stream half work: more revenue now means proportionally more staff.

    Clamps to the NEAREST EDGE of the band, not the middle, so a defensible figure the AI
    chose is nudged the minimum distance. Guarded so the correction can never push EBITDA
    below _MIN_EBITDA_MARGIN, and never applied to the capacity family (Bank Loan).
    """
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        m = get_operating_model(getattr(project, "industry", "") or "")
    except Exception:
        return out
    if not m or getattr(m, "family", "") != "volume_price":
        return out
    band = getattr(m, "labour_pct", None)
    if not band:
        return out
    lo, hi = band

    core = (_num(out.get(_CAPACITY)) or 0.0) * (_num(out.get(_PRICE)) or 0.0)
    streams = sum((_num(out.get(v)) or 0.0) * (_num(out.get(p)) or 0.0)
                  for v, p in zip(_STREAM_VOL_CELLS, _STREAM_PRICE_CELLS))
    revenue = core + streams
    wages = _num(out.get(_WAGES_CELL))
    if revenue <= 0 or wages is None:
        return out

    pct = (wages * 12.0) / revenue
    target = lo if pct < lo else (hi if pct > hi else None)
    if target is None:
        return out

    # What else the year already consumes, so the clamp cannot bury the business.
    gm = _num(out.get(_GM_CELL)) or 0.0
    cost_of_sales = revenue * (1.0 - gm) if 0 < gm <= 1 else 0.0
    other_fixed = 12.0 * sum(_num(out.get(c)) or 0.0 for c in _OTHER_FIXED)
    selling = revenue * (_num(out.get(_SELLING_CELL)) or 0.0)
    headroom = revenue - cost_of_sales - other_fixed - selling - revenue * _MIN_EBITDA_MARGIN

    current_annual = wages * 12.0
    new_annual = revenue * target
    if new_annual > headroom:
        # Not enough room to reach the band without burying the business. Go as far as
        # the floor allows — but NEVER past the figure we started from: this branch
        # exists to raise under-stated wages, and letting the cap fall below the current
        # value would silently CUT them, which is the opposite of the fix.
        new_annual = max(headroom, current_annual)
        logger.info("labour: %s clamp capped by the EBITDA floor at %.1f%% of revenue "
                    "(band wanted %.0f%%)", m.display_name,
                    100.0 * new_annual / revenue, 100.0 * target)
    if new_annual <= 0 or abs(new_annual - current_annual) < 1:
        return out
    out[_WAGES_CELL] = round(new_annual / 12.0)
    logger.info("labour: %s wages %.1f%% of revenue -> %.1f%% (band %.0f-%.0f%%)",
                m.display_name, 100.0 * pct, 100.0 * new_annual / revenue,
                100.0 * lo, 100.0 * hi)
    return out


_SEGMENT_ROWS = range(58, 63)
_SEG_NAME = "Assumptions!C{}"
_SEG_SHARE = "Assumptions!D{}"


def reconcile_segments(answers: dict, project=None) -> dict:
    """Make the target-market revenue split add up to exactly 100%.

    The Sales sheet apportions Net Sales by these shares, so anything other than 1.0
    means the segment table would not tie to revenue — the first thing a reader checks.
    Only segments that actually carry a name are counted; a share on an unnamed row is
    dropped rather than silently inflating the split.

    If the AI named NO segment at all the table would render blank, which reads as a
    missing analysis rather than a deliberate one. In that case the industry's own
    default_segments seed it (a hotel gets leisure/corporate/groups, a hospital gets
    OPD/IPD/insurance), so the split is always present and always ties to Net Sales."""
    if not isinstance(answers, dict):
        return answers
    out = dict(answers)
    named = []
    for r in _SEGMENT_ROWS:
        name = out.get(_SEG_NAME.format(r))
        share = _num(out.get(_SEG_SHARE.format(r))) or 0.0
        if isinstance(name, str) and name.strip():
            named.append((r, share))
        else:
            out.pop(_SEG_NAME.format(r), None)
            out.pop(_SEG_SHARE.format(r), None)
    if not named:
        defaults = ()
        try:
            from financial_engine.industry_calc.operating_models import get_operating_model
            m = get_operating_model(getattr(project, "industry", "") or "")
            if m and getattr(m, "family", "") == "volume_price":
                defaults = getattr(m, "default_segments", ()) or ()
        except Exception:
            defaults = ()
        if not defaults:
            return out
        for r, (nm, sh) in zip(_SEGMENT_ROWS, defaults):
            out[_SEG_NAME.format(r)] = nm
            out[_SEG_SHARE.format(r)] = sh
        logger.info("segments: none named; seeded %d industry-default segments", len(defaults))
        return out
    total = sum(s for _, s in named)
    if total <= 0:
        even = round(1.0 / len(named), 4)
        for r, _ in named:
            out[_SEG_SHARE.format(r)] = even
        logger.info("segments: no usable shares; split evenly across %d segments", len(named))
        return out
    if abs(total - 1.0) > 0.005:
        for r, s in named:
            out[_SEG_SHARE.format(r)] = round(s / total, 4)
        logger.info("segments: shares summed to %.3f; normalised to 1.0", total)
    return out


def reconcile_phasing(answers: dict, project) -> dict:
    """Give the 12 monthly phasing weights (Assumptions C21:N21) a gentle intra-year ramp
    instead of the flat, all-equal values the AI tends to fill — otherwise every month of a
    year is identical (e.g. 29, 29, 29 …), which reads as fake.

    The weights only redistribute each year's volume across its 12 months; the sheet
    normalises by their sum (monthly = annual/12 × 12·wₘ/Σw), so the ANNUAL total is
    unchanged to the rupee. Every annual figure, DSCR and balance-sheet line is therefore
    untouched — only the monthly shape changes.

    Scoped to software/technology for now, and deliberately skipped for manufacturing so the
    Bank Loan reference keeps its exact current (flat) monthly rows. A genuinely varied
    (seasonal) pattern that is already present is respected, not overwritten.
    """
    if not isinstance(answers, dict):
        return answers
    # Apply to every volume-price (service) industry; skip the capacity family
    # (manufacturing / textile / auto / mining), which routes to the frozen Bank Loan base
    # and must keep its exact flat monthly rows.
    try:
        from financial_engine.industry_calc.operating_models import get_operating_model
        family = getattr(get_operating_model(getattr(project, "industry", "") or ""), "family", "")
    except Exception:
        family = ""
    if family != "volume_price":
        return answers
    cols = "CDEFGHIJKLMN"
    keys = [f"Assumptions!{c}21" for c in cols]
    nums = [answers.get(k) for k in keys]
    present = [float(v) for v in nums if isinstance(v, (int, float))]
    # Only step in when the weights are missing or all identical (the flat default).
    if len(present) >= 2 and len({round(v, 6) for v in present}) > 1:
        return answers
    # Gentle linear ramp 0.75 → 1.25. Mean is exactly 1.0 (Σ = 12), so the annual total is
    # preserved; month 1 ≈ 0.75× the average, month 12 ≈ 1.25×.
    ramp = [round(0.75 + i * (0.5 / 11), 4) for i in range(12)]
    for k, w in zip(keys, ramp):
        answers[k] = w
    logger.info("phasing: applied gentle monthly ramp (family=%r, annual unchanged)", family)
    return answers


def financing_check(answers: dict, project) -> dict:
    """A plain sources-vs-uses statement for logging / display. Never raises."""
    uses = sum((_num(answers.get(c)) or 0.0) for c, _, _ in _ASSET_CELLS)
    sources = (_num(answers.get(_LOAN_CELL)) or 0.0) + (_num(answers.get(_EQUITY_CELL)) or 0.0)
    return {
        "uses_cost_of_project": uses,
        "sources_loan_plus_equity": sources,
        "gap": sources - uses,
        "ties": abs(sources - uses) <= 0.02 * max(sources, uses, 1),
        "stated_project_cost": _num(getattr(project, "project_cost", None)),
    }
