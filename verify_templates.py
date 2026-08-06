"""
verify_templates.py

Every fix, asserted against every template.  Run it after ANY change to a workbook:

    python verify_templates.py

Why this file exists
--------------------
Fixes in this project are migration scripts run against eleven .xlsx binaries. There is no
compiler and no import graph to catch a template that missed one, so for a long time each
feature carried only its OWN check. That let a fix silently disappear:

  * The monthly-moratorium fix was applied to the ten industry templates and deliberately
    NOT to bank_loan, to keep Bank Loan byte-identical. That reason expired the day
    bank_loan was rebuilt at the client's request — but nobody went back for it, and a
    manufacturing report kept repaying principal straight through its holiday period
    (Year-1 principal doubled, DSCR Yr1 read 1.75 instead of 2.61).

  * Several migrations restore from their own .bak before applying, so they can be re-run
    safely. That is only true in isolation: if migration A's backup predates migration B,
    re-running A silently reverts B.

Neither failure is visible in a single report. Both are obvious here.

Add a check whenever you add a fix. A check returns None when the invariant holds, or a
short string describing what is wrong.
"""

from __future__ import annotations

import glob
import os
import re
import sys
import zipfile

import openpyxl

BACKEND = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(BACKEND, "templates")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

FOLDERS = ["bank_loan", "hotel_cma", "retail_cma", "software_cma", "hospital_cma",
           "education_cma", "restaurant_cma", "trading_cma", "transport_cma",
           "media_cma", "other_cma"]

CHECKS: dict[str, callable] = {}


def check(name):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


@check("moratorium honoured in the monthly repayment schedule")
def _(folder, path, wb):
    if "Repayment" not in wb.sheetnames:
        return "no Repayment sheet"
    rp = wb["Repayment"]
    flat, guarded = [], 0
    for r in range(20, min(rp.max_row, 60) + 1):
        for c in range(3, 16):
            v = rp.cell(r, c).value
            if not isinstance(v, str) or not v.startswith("="):
                continue
            if re.fullmatch(r"=\$[A-Z]\$\d+/12", v.strip()):
                flat.append(f"{rp.cell(r, c).coordinate}={v}")
            elif "$C$12" in v:
                guarded += 1
    if flat and not guarded:
        return f"flat /12 principal repays through the moratorium (e.g. {flat[0]})"
    if not guarded:
        return "no moratorium term ($C$12) in the monthly schedule"
    return None


@check("revenue streams have both a volume and a price cell")
def _(folder, path, wb):
    a = wb["Assumptions"]
    missing = [f"{col}{r}" for r in range(66, 70) for col in ("C", "D")
               if a.cell(r, 3 if col == "C" else 4).value is None]
    return f"missing driver cells {missing}" if missing else None


@check("target-market segment block present")
def _(folder, path, wb):
    return None if wb["Assumptions"].cell(58, 2).value else "no segment rows at B58"


@check("existing-loan inputs and sheet present")
def _(folder, path, wb):
    if "Existing Loan" not in wb.sheetnames:
        return "no 'Existing Loan' sheet"
    a = wb["Assumptions"]
    for r, what in ((72, "treatment"), (73, "outstanding"), (74, "rate"), (75, "tenure")):
        if a.cell(r, 3).value is None:
            return f"Assumptions C{r} ({what}) missing"
    return None


@check("existing loan wired into P&L, balance sheet, DSCR and fund flow")
def _(folder, path, wb):
    for sheet, row in (("Expenses", 14), ("Form_III_BalanceSheet", 9),
                       ("DSCR", 11), ("Form_VI_FundFlow", 14)):
        if sheet not in wb.sheetnames:
            return f"{sheet} missing"
        ws = wb[sheet]
        if not any(isinstance(ws.cell(row, c).value, str)
                   and "Existing Loan" in ws.cell(row, c).value
                   for c in range(2, min(ws.max_column, 70) + 1)):
            return f"{sheet} row {row} does not read 'Existing Loan'"
    return None


@check("WC sheet: labels in column B, linked to the model, loan split present")
def _(folder, path, wb):
    if "WC & CC-OD Limit" not in wb.sheetnames:
        return "sheet missing"
    ws = wb["WC & CC-OD Limit"]
    if ws.cell(6, 2).value is None and ws.cell(6, 1).value is not None:
        return "labels are in column A — the wide-gap layout is back"
    if "TERM LOAN" not in " ".join(str(ws.cell(r, 2).value or "")
                                   for r in range(1, 40)).upper():
        return "no term-loan vs working-capital split"
    if not isinstance(ws.cell(6, 3).value, str) or "Form_IV" not in ws.cell(6, 3).value:
        return "not linked to the model — dead blue inputs again"
    return None


@check("inventory schedule exactly where the industry carries stock")
def _(folder, path, wb):
    from financial_engine.industry_calc.operating_models import get_operating_model
    m = get_operating_model({"bank_loan": "manufacturing"}.get(
        folder, folder.replace("_cma", "")))
    has = "Inventory Schedule" in wb.sheetnames
    if m and m.holds_inventory and not has:
        return "industry holds stock but has no Inventory Schedule"
    if m and not m.holds_inventory and has:
        return "industry holds no stock but has an Inventory Schedule"
    return None


@check("SWOT sheet stays removed")
def _(folder, path, wb):
    return "SWOT sheet is back" if "SWOT" in wb.sheetnames else None


@check("one revenue sheet, no mirror")
def _(folder, path, wb):
    if folder == "bank_loan":
        return None if "Sales" in wb.sheetnames else "no Sales sheet"
    if "Revenue Plan" in wb.sheetnames:
        return "the Revenue Plan mirror is back"
    return None if "Revenue Build-Up" in wb.sheetnames else "no Revenue Build-Up"


@check("no formula points at a sheet that does not exist")
def _(folder, path, wb):
    names = set(wb.sheetnames)
    bad = {ref for ws in wb.worksheets for row in ws.iter_rows() for c in row
           if isinstance(c.value, str) and c.value.startswith("=")
           for ref in re.findall(r"'([^']+)'!", c.value) if ref not in names}
    return f"dangling references to {sorted(bad)}" if bad else None


@check("every chart series resolves")
def _(folder, path, wb):
    names = set(wb.sheetnames)
    bad = set()
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if "/charts/chart" in n:
                for m in re.findall(r"<f>([^<]+)</f>", z.read(n).decode("utf8", "ignore")):
                    if "!" in m and m.split("!")[0].strip("'") not in names:
                        bad.add(m.split("!")[0].strip("'"))
    return f"charts point at {sorted(bad)}" if bad else None


def main() -> int:
    results = []
    for folder in FOLDERS:
        matches = glob.glob(os.path.join(TEMPLATES, folder, "*.xlsx"))
        if not matches:
            results += [(folder, n, "no workbook on disk") for n in CHECKS]
            continue
        path = matches[0]
        wb = openpyxl.load_workbook(path)
        for name, fn in CHECKS.items():
            try:
                results.append((folder, name, fn(folder, path, wb)))
            except Exception as exc:                       # a broken check is a failure
                results.append((folder, name, f"check errored: {type(exc).__name__}: {exc}"))

    width = max(len(n) for n in CHECKS) + 2
    print(f"{'invariant':<{width}}" + "".join(f"{f.replace('_cma', ''):>12}" for f in FOLDERS))
    print("-" * (width + 12 * len(FOLDERS)))
    failures = 0
    for name in CHECKS:
        line = f"{name:<{width}}"
        for folder in FOLDERS:
            problem = next(p for (f, n, p) in results if f == folder and n == name)
            line += f"{('ok' if problem is None else 'FAIL'):>12}"
            failures += problem is not None
        print(line)

    seen = set()
    detail = [(n, p) for (_, n, p) in results if p and (n, p) not in seen
              and not seen.add((n, p))]
    if detail:
        print("\ndetail:")
        for name, problem in detail:
            who = sorted({f for (f, n, p) in results if n == name and p == problem})
            print(f"  [{name}]\n     {problem}\n     affects: {who}")

    print(f"\n{'ALL INVARIANTS HOLD' if not failures else f'{failures} FAILING CELLS'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
