"""
generation_router.py

Purpose-driven generation pipeline. The selected purpose decides the
methodology, report sections, workbook sheets and charts (see purpose_config).

Endpoints (all require auth + project ownership):
  POST /generate/{project_id}            -> run agents + build structured model, persist
  GET  /generate/{project_id}/excel      -> stream the .xlsx workbook
  GET  /generate/{project_id}/word       -> stream the .docx report
"""

import json
import logging
import re
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.project_model import Project
from models.report_model import Report
from models.questionnaire_model import QuestionnaireAnswer
from dependencies import get_owned_project

from purpose_config import resolve_purpose, get_config
from template_config import default_template, get_template, find_template_by_id, template_path
from services.financial_model_service import generate_financial_model
from services.excel_builder import build_excel
from services.excel_model_builder import build_model_excel
from services.word_builder import build_word
from services.sample_blueprint_service import build_blueprint_text, has_sample
from services.template_fill_service import fill_template, template_filename
from services.template_model_service import generate_template_inputs, derive_headline_kpis
from services.template_introspect import load_schema
from services.recalc_service import libreoffice_available, recalculate_xlsx, read_computed_kpis
from services.template_analysis import load_analysis, extract_kpis, run_checks
from agents.market_research_agent import market_research_agent
from agents.feasibility_agent import feasibility_agent
from agents.swot_agent import swot_agent

router = APIRouter(prefix="/generate", tags=["Generation"])
logger = logging.getLogger("generation")

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSM_MIME = "application/vnd.ms-excel.sheet.macroEnabled.12"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

_PROJECT_FIELDS = [
    "id", "title", "industry", "sub_industry", "country", "currency", "location",
    "promoter_name", "promoter_experience", "project_description", "target_market",
    "target_customers", "project_cost", "own_contribution", "loan_amount", "purpose",
    "financial_format", "created_at",
]


class GenerateRequest(BaseModel):
    purpose_answers: dict = {}
    # Which sample template the user picked (see template_config). Cell-keyed
    # answers ("Sheet!Cell": value) inside purpose_answers fill that template.
    template_id: str | None = None


# Reserved key used to remember the chosen template inside the persisted answers.
_TEMPLATE_KEY = "_template_id"


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", (text or "report")).strip("_")[:40] or "report"


def _stored_answers(db: Session, project: Project) -> dict:
    """Load persisted questionnaire answers for a project (or {})."""
    q = db.query(QuestionnaireAnswer).filter(QuestionnaireAnswer.project_id == project.id).first()
    if q and q.collected_data:
        try:
            return json.loads(q.collected_data)
        except (ValueError, TypeError):
            return {}
    return {}


def _persist_answers(db: Session, project: Project, answers: dict) -> None:
    """Upsert the project's questionnaire answers (incl. AI-generated cell values)."""
    q = db.query(QuestionnaireAnswer).filter(QuestionnaireAnswer.project_id == project.id).first()
    payload = json.dumps(answers or {})
    if q:
        q.collected_data = payload
    else:
        db.add(QuestionnaireAnswer(project_id=project.id, collected_data=payload))
    db.commit()


def _resolve_template(purpose_key: str, answers: dict):
    """The template to fill: the user's explicitly chosen one (looked up by its
    globally-unique id, regardless of purpose), else the purpose's default.
    Returns (purpose_key, template) or (purpose_key, None) if none applies."""
    tid = (answers or {}).get(_TEMPLATE_KEY)
    if tid:
        tpurpose, t = find_template_by_id(tid)
        if t and t.get("engine") == "template_fill":
            return tpurpose, t
    return purpose_key, default_template(purpose_key)


def _project_dict(project: Project, answers: dict) -> dict:
    d = {f: getattr(project, f, None) for f in _PROJECT_FIELDS}
    d["purpose_answers"] = answers or {}
    return d


def _enriched_description(project: Project, purpose_key: str, answers: dict) -> str:
    """Feed purpose + questionnaire answers into the existing agents (no new
    agent, no signature change) by enriching the description text."""
    cfg = get_config(purpose_key)
    lines = [project.project_description or ""]
    lines.append(f"\nREPORT PURPOSE: {cfg['label']}")
    if answers:
        lines.append("KEY FINANCIAL INPUTS: " + json.dumps(answers))
    return "\n".join(lines)


def _build_agent_context(project: Project, purpose_key: str, answers: dict) -> str:
    """Reuse the existing agents to produce supporting analysis, now purpose-aware.

    The three agents are independent, so we run them concurrently (each call is
    blocking network I/O) to cut total latency from sum-of-three to ~one call.
    """
    from concurrent.futures import ThreadPoolExecutor

    name = project.title or "the business"
    industry = project.industry or "General"
    country = project.country or "India"
    desc = _enriched_description(project, purpose_key, answers)
    pc = project.project_cost or 0
    oc = project.own_contribution or 0
    loan = project.loan_amount or 0
    label = get_config(purpose_key)["label"]

    def _safe(title, fn):
        try:
            return f"{title}:\n" + fn()
        except Exception as e:  # agent failures must not abort generation
            return f"{title}: (unavailable: {e})"

    tasks = {
        "MARKET RESEARCH": lambda: market_research_agent(
            business_name=name, industry=industry, country=country, purpose=label, description=desc),
        "FEASIBILITY": lambda: feasibility_agent(
            business_name=name, industry=industry, country=country,
            description=desc, project_cost=pc, own_contribution=oc, loan_amount=loan),
        "SWOT": lambda: swot_agent(
            business_name=name, industry=industry, country=country, description=desc),
    }

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {title: pool.submit(_safe, title, fn) for title, fn in tasks.items()}
        # Preserve a stable order in the combined context.
        parts = [futures[title].result() for title in ("MARKET RESEARCH", "FEASIBILITY", "SWOT")]
    return "\n\n".join(parts)


def _preview_markdown(model: dict, purpose_key: str, project: Project) -> str:
    """On-screen preview: narrative + financial tables (so the report viewer can
    render charts). The downloadable Word omits the heavy tables; Excel is the
    authoritative model."""
    cfg = get_config(purpose_key)
    md = [f"# {project.title or 'Project Report'}", f"_{cfg['label']}_\n"]

    kpis = model.get("kpis") or []
    if kpis:
        md.append("## Key Indicators\n")
        md.append("| Indicator | Value |\n|---|---|")
        for k in kpis[:16]:
            md.append(f"| {k.get('label','')} | {k.get('value','')} |")
        md.append("")

    narrative = model.get("narrative") or {}
    for sec in cfg["word_sections"]:
        md.append(f"## {sec['title']}\n")
        md.append(str(narrative.get(sec["title"]) or "_See the Excel financial model for details._"))
        md.append("")

    sheets = model.get("sheets") or []
    if sheets:
        md.append("## Financial Statements\n")
        for s in sheets:
            cols = s.get("columns") or []
            rows = s.get("rows") or []
            if not cols or not rows:
                continue
            md.append(f"### {s.get('name','')}\n")
            md.append("| " + " | ".join(str(c) for c in cols) + " |")
            md.append("|" + "|".join("---" for _ in cols) + "|")
            for r in rows:
                cells = [str(r[i]) if i < len(r) else "" for i in range(len(cols))]
                md.append("| " + " | ".join(cells) + " |")
            md.append("")
    return "\n".join(md)


def _load_model(project: Project) -> dict:
    report = project.report
    if not report or not report.financial_model:
        raise HTTPException(status_code=404, detail="No financial model yet. Generate the report first.")
    try:
        return json.loads(report.financial_model)
    except (ValueError, TypeError):
        raise HTTPException(status_code=500, detail="Stored financial model is corrupted. Re-generate the report.")


@router.post("/{project_id}")
def generate(req: GenerateRequest, project: Project = Depends(get_owned_project),
             db: Session = Depends(get_db)):
    purpose_key = resolve_purpose(project.purpose, project.financial_format)

    # Gather the chatbot/questionnaire answers (prefer this request, else stored).
    answers = dict(req.purpose_answers or {})
    if req.template_id:
        answers[_TEMPLATE_KEY] = req.template_id
    if not answers:
        answers = _stored_answers(db, project)

    agent_context = _build_agent_context(project, purpose_key, answers)

    # AI generates the user's OWN model as values for the template's input cells.
    # The sample workbook is a DESIGN BLUEPRINT only — we never keep its numbers.
    # Any cell value the user supplied explicitly (form) overrides the AI value.
    tpurpose, template = _resolve_template(purpose_key, answers)
    # Headline KPIs derived directly from the template's input cells (kept exact and
    # consistent with the editable Excel). Overrides the LLM's free-form KPIs for
    # template-fill purposes so the Word report never quotes a figure the Excel model
    # would contradict.
    derived_kpis = None
    consistency = None
    # Only AI-fill a template when its sample workbook still exists on disk. If the
    # samples were removed, skip the template track entirely and let the
    # deterministic formula-driven model (build_model_excel) be the output.
    if template and template_path(tpurpose, template["id"]):
        ai_inputs = {}
        try:
            ai_inputs = generate_template_inputs(
                _project_dict(project, answers), tpurpose, template["id"], agent_context)
        except Exception as e:
            logger.exception("generate: AI template-input generation errored")
        user_cells = [k for k in answers if "!" in k]
        # Never ship the untouched sample: if the AI produced no values (and the
        # user supplied none), fail loudly instead of returning the sample as-is.
        if not ai_inputs and not user_cells:
            raise HTTPException(
                status_code=502,
                detail="AI could not generate the financial-model inputs for this template. Please try again.",
            )
        answers = {**ai_inputs, **answers}  # user-provided "Sheet!Cell" values win
        logger.info("generate: project=%s AI-filled %d input cells for %s/%s",
                    project.id, len(ai_inputs), tpurpose, template["id"])
        tschema = load_schema(tpurpose, template["id"])
        if tschema:
            # Input-derived headline figures (exact, always available) as the baseline.
            derived_kpis = derive_headline_kpis(tschema, answers)
        # Template-driven analysis map (auto-detected KPI + consistency-check cells).
        analysis = load_analysis(tpurpose, template["id"])
        # If LibreOffice is present, recalculate the filled workbook ONCE on the server
        # and (a) read the EXACT computed metrics (DSCR/IRR/NPV/ROI/ratios) so every
        # output uses one set of numbers, and (b) run the template's consistency checks
        # (Sources=Uses / balance = 0). Non-fatal: on any failure we keep the input-
        # derived figures and generation still succeeds.
        legacy_kpis = bool(tschema and tschema.get("computed_kpis"))
        if libreoffice_available() and (analysis.get("kpis") or analysis.get("checks") or legacy_kpis):
            try:
                recalc = recalculate_xlsx(fill_template(tpurpose, template["id"], answers))
                kpis = extract_kpis(recalc, analysis)
                if not kpis and legacy_kpis:            # legacy hand-wired templates
                    kpis = read_computed_kpis(tschema, recalc)
                if kpis:
                    derived_kpis = kpis
                consistency = run_checks(recalc, analysis)
                logger.info("generate: project=%s recalc KPIs=%d checks=%s", project.id,
                            len(kpis), {c["name"][:22]: c["ok"] for c in (consistency or [])})
            except Exception:
                logger.warning("generate: server recalc/analysis failed; using input-derived KPIs",
                               exc_info=True)

    _persist_answers(db, project, answers)

    # Ground the narrative in the exact, input-derived figures so the prose can't
    # quote numbers that disagree with the Excel model; defer computed ratios to it.
    if derived_kpis:
        verified = "\n".join(f"- {k['label']}: {k['value']}" for k in derived_kpis)
        agent_context += (
            "\n\nVERIFIED HEADLINE FIGURES (use these EXACT numbers in the narrative; "
            "do NOT invent different ones. For DSCR, IRR, NPV and detailed year-by-year "
            "ratios, refer the reader to the accompanying Excel model rather than quoting "
            "a specific figure):\n" + verified)

    sample_blueprint = build_blueprint_text(purpose_key) or ""
    try:
        model = generate_financial_model(_project_dict(project, answers), purpose_key,
                                         agent_context, sample_blueprint=sample_blueprint)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model generation failed: {e}")

    # Prefer the exact, recalculated headline KPIs for template-fill purposes so the
    # Word/preview figures stay consistent with the Excel model.
    if derived_kpis:
        model["kpis"] = derived_kpis
    if consistency is not None:
        model["consistency_checks"] = consistency

    preview = _preview_markdown(model, purpose_key, project)

    # Persist on the project's report row.
    report = project.report
    if not report:
        report = Report(project_id=project.id)
        db.add(report)
    report.report_content = preview
    report.financial_model = json.dumps(model)
    report.financial_format = purpose_key
    report.status = "completed"
    project.status = "completed"
    db.commit()

    return {
        "purpose": purpose_key,
        "purpose_label": get_config(purpose_key)["label"],
        "report_content": preview,
        "kpis": model.get("kpis", []),
        "consistency_checks": model.get("consistency_checks", []),
        "sheet_names": [s.get("name") for s in model.get("sheets", [])],
    }


@router.get("/{project_id}/excel")
def download_excel(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    purpose_key = resolve_purpose(project.purpose, project.financial_format)
    answers = _stored_answers(db, project)

    tpurpose, template = _resolve_template(purpose_key, answers)
    # Only use template-fill when the sample workbook actually exists on disk.
    # If the samples were removed, fall through to the deterministic formula-driven
    # model (build_model_excel), which needs no sample and never 502s.
    if template and template_path(tpurpose, template["id"]):
        # Template-fill: hand back the real sample workbook with the user's
        # inputs written into its input cells; every formula/chart is preserved
        # and Excel recomputes the whole model on open.
        logger.info("excel: project=%s purpose=%s -> template-fill %s/%s",
                    project.id, purpose_key, tpurpose, template["id"])
        try:
            data = fill_template(tpurpose, template["id"], answers)
        except Exception as e:
            # fill_template validates the workbook and raises on any corruption,
            # so we return an error rather than ever streaming a broken file.
            logger.exception("excel: template fill failed for project %s", project.id)
            raise HTTPException(status_code=502, detail=f"Template fill failed: {e}")
        # Serve the RECALCULATED workbook so it already carries computed values, not
        # just formulas. Non-fatal: if LibreOffice is unavailable we serve the filled
        # file and Excel recomputes on open (fullCalcOnLoad is set).
        if libreoffice_available():
            try:
                data = recalculate_xlsx(data)
            except Exception:
                logger.warning("excel: server recalc failed; serving filled workbook", exc_info=True)
        fname = template_filename(tpurpose, template["id"], f"{_slug(project.title)}_financial_model")
        media = XLSM_MIME if fname.endswith(".xlsm") else XLSX_MIME
        logger.info("excel: streaming %s (%d bytes, %s)", fname, len(data), media)
        return StreamingResponse(BytesIO(data), media_type=media,
                                 headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    if has_sample(purpose_key):
        # Sample-driven purpose (no template-fill template): mirror the sample's
        # structure using the LLM-built model.
        model = _load_model(project)
        data = build_excel(model, purpose_key, _project_dict(project, {}))
    else:
        # Deterministic, fully formula-driven model. Assumptions are derived from
        # the project + questionnaire answers; every other cell is an Excel formula.
        data = build_model_excel(_project_dict(project, answers))

    fname = f"{_slug(project.title)}_financial_model.xlsx"
    return StreamingResponse(BytesIO(data), media_type=XLSX_MIME,
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _build_word_report(project: Project, db: Session):
    """The Word report bytes + base filename. For an uploaded Word (.docx) template
    this fills its {{placeholders}}; otherwise it builds the narrative report from the
    stored model (whose KPIs are the server-recalculated, consistent values)."""
    purpose_key = resolve_purpose(project.purpose, project.financial_format)
    answers = _stored_answers(db, project)
    tpurpose, template = _resolve_template(purpose_key, answers)
    if template and template.get("engine") == "docx_fill" and template_path(tpurpose, template["id"]):
        from services.docx_fill_service import fill_docx
        ctx = {f: getattr(project, f, None) for f in _PROJECT_FIELDS}
        for k, v in answers.items():
            # answer keys are "Sheet!Cell"; docx placeholder names carry no sheet
            ctx[k.split("!", 1)[1] if "!" in k else k] = v
        data = fill_docx(template_path(tpurpose, template["id"]), ctx)
        return data, f"{_slug(project.title)}_{template['id']}"
    model = _load_model(project)
    data = build_word(model, purpose_key, _project_dict(project, {}))
    return data, f"{_slug(project.title)}_{purpose_key}"


@router.get("/{project_id}/word")
def download_word(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    try:
        data, base = _build_word_report(project, db)
    except Exception as e:
        logger.exception("word: report build failed for project %s", project.id)
        raise HTTPException(status_code=502, detail=f"Word report failed: {e}")
    return StreamingResponse(BytesIO(data), media_type=DOCX_MIME,
                             headers={"Content-Disposition": f'attachment; filename="{base}.docx"'})


@router.get("/{project_id}/pdf")
def download_pdf(project: Project = Depends(get_owned_project), db: Session = Depends(get_db)):
    """PDF of the report, rendered by LibreOffice from the SAME Word document that the
    .docx download produces — so the PDF, Word and Excel all carry identical figures."""
    from services.recalc_service import to_pdf, libreoffice_available
    if not libreoffice_available():
        raise HTTPException(
            status_code=503,
            detail="PDF export needs LibreOffice on the server (set LIBREOFFICE_PATH).")
    try:
        word, base = _build_word_report(project, db)
        data = to_pdf(word, "docx")
    except Exception as e:
        logger.exception("pdf: export failed for project %s", project.id)
        raise HTTPException(status_code=502, detail=f"PDF export failed: {e}")
    return StreamingResponse(BytesIO(data), media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{base}.pdf"'})
