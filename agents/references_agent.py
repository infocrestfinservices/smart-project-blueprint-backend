"""Sources for the non-financial content of the report.

A banker reading a market section asks where the numbers came from. This agent produces
the reference list that answers that: current publications with working links, plus the
standard books, which have no currency requirement — a text on project appraisal is as
good in its fourth edition as its sixth.

Two things are deliberately not claimed. The model recalls these sources, it does not
search for them, so every URL is checked for a live response before it is printed and a
dead link is dropped rather than shown. And a reachable link proves the page exists, not
that it says what the report says — the entries are pointed at the publisher's own landing
pages, which stay put, rather than at deep report URLs that rot within a year.
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from services.claude_service import invoke_llm

logger = logging.getLogger(__name__)

# Online sources must be this recent. Books are exempt — see the module docstring.
MIN_YEAR = 2025

_PROMPT = """You are a research librarian preparing the reference list for a bank-grade
project appraisal report.

Business: {business_name}
Industry: {industry}
Location: {location}
Country: {country}
Description: {description}

List the sources a professional would actually cite for the MARKET, INDUSTRY, REGULATORY
and BENCHMARKING content of a report on this business in this location.

HARD RULES:
1. Every source that is NOT a book must be dated {min_year} or later. Nothing older.
   If you are not confident a publication has a {min_year}+ edition, leave it out.
2. INCLUDE AT LEAST TWO BOOKS — the standard professional texts a CA or credit officer
   actually works from (project appraisal and financing, credit and working-capital
   management, financial statement analysis, and where one exists the standard text for
   this industry). Give title, author and publisher. Books have NO year requirement and
   need no URL: a good text is a good text in any edition.
3. Give the URL of the PUBLISHER'S OWN stable page (the organisation's site, its
   publications index, or the statute's official page). Do NOT invent deep links to
   individual PDFs — they rot and a broken link in front of a banker is worse than none.
   Books need no URL.
4. Only sources you are confident genuinely exist. A short, real list beats a long,
   invented one.
5. Prefer authoritative bodies for {country}: the central bank, the national statistics
   office, the relevant ministry, the industry's own association or council, development
   banks, and recognised industry-data publishers. Include the specific regulator or
   licensing authority for this industry where one applies.

Return ONLY a JSON array, no commentary, of 8 to 14 objects:
[
  {{"kind": "report|statistics|regulation|article|website|book",
    "title": "exact title",
    "author": "author, for books; omit otherwise",
    "publisher": "issuing organisation or publisher",
    "year": "{min_year} or later; a book's own year",
    "url": "stable publisher URL; omit for books",
    "note": "at most 12 words on what it was used for"}}
]"""


def _sources(project: dict) -> list:
    prompt = _PROMPT.format(
        business_name=project.get("title") or project.get("business_name") or "the business",
        industry=project.get("industry") or "N/A",
        location=project.get("location") or "N/A",
        country=project.get("country") or "India",
        description=(project.get("description") or "")[:600],
        min_year=MIN_YEAR,
    )
    raw = invoke_llm(prompt) or ""
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        raise ValueError("references: no JSON array in model output")
    return json.loads(m.group(0))


def _is_live(url: str) -> bool:
    """True if the URL answers. A 403/405 still means the host is there and serving."""
    try:
        import httpx
        with httpx.Client(timeout=6.0, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"}) as c:
            try:
                r = c.head(url)
                if r.status_code >= 400:
                    r = c.get(url)
            except Exception:
                r = c.get(url)
        return r.status_code < 400 or r.status_code in (403, 405, 406, 429)
    except Exception:
        return False


def _clean(items) -> list:
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not str(it.get("title") or "").strip():
            continue
        kind = str(it.get("kind") or "website").strip().lower()
        year = str(it.get("year") or "").strip()
        digits = re.search(r"(19|20)\d{2}", year)
        # Currency rule, applied here and not left to the model's good intentions.
        if kind != "book":
            if not digits or int(digits.group(0)) < MIN_YEAR:
                continue
        url = str(it.get("url") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            url = ""
        out.append({"kind": kind, "title": str(it["title"]).strip(),
                    "author": str(it.get("author") or "").strip(),
                    "publisher": str(it.get("publisher") or "").strip(),
                    "year": digits.group(0) if digits else year,
                    "url": url, "note": str(it.get("note") or "").strip()})
    return out


def references_agent(project: dict) -> list:
    """The reference list, with every surviving URL verified reachable. [] on any failure."""
    try:
        refs = _clean(_sources(project))
    except Exception:
        logger.warning("references: could not build the source list", exc_info=True)
        return []
    # The currency rule drops sources silently, and a run that loses all of its books is
    # worth knowing about — the list is meant to carry standard texts as well as links.
    if not any(r["kind"] == "book" for r in refs):
        logger.info("references: no books in the list for %s", project.get("title"))

    urls = [r["url"] for r in refs if r["url"]]
    live = {}
    if urls:
        with ThreadPoolExecutor(max_workers=8) as pool:
            live = dict(zip(urls, pool.map(_is_live, urls)))
    dropped = 0
    for r in refs:
        if r["url"] and not live.get(r["url"]):
            r["url"] = ""
            dropped += 1
    logger.info("references: %d sources, %d links checked, %d unreachable dropped",
                len(refs), len(urls), dropped)
    return refs
