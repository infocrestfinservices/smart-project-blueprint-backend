"""
template_model_service.py

Generates the user's OWN financial model as a set of input-cell values for a
chosen sample template. The sample is a DESIGN BLUEPRINT only — we never keep its
business numbers. The AI reads all the chatbot/questionnaire answers, computes
realistic assumptions for THIS business, and returns one value per input cell.
Those values are written into the template's input cells; the template's own
formulas then recompute every dependent sheet, chart, KPI and ratio.

So the division of labour is:
  - AI  -> the input assumptions/drivers for the user's business
  - the sample's formulas -> every derived statement (P&L, cash flow, IRR, …)

This keeps the model mathematically consistent (the template guarantees it) while
guaranteeing the output represents the user's business, not the sample's.
"""

import json
import logging

from services.claude_service import invoke_llm
from services.financial_model_service import _extract_json
from services.template_introspect import load_schema
from services.template_fill_service import field_key

logger = logging.getLogger("template_model")

# Cap how many input cells we ask the model to fill in one shot (very large
# templates are chunked so the request stays reliable).
_MAX_FIELDS_PER_CALL = 90


def _project_summary(project: dict) -> str:
    """A compact, complete dump of everything we know about the user's business."""
    answers = project.get("purpose_answers") or {}
    # Drop internal control keys from the answers we show the model.
    answers = {k: v for k, v in answers.items() if "!" not in k and not k.startswith("_")}
    lines = [
        f"Business name: {project.get('title')}",
        f"Industry: {project.get('industry')} / {project.get('sub_industry')}",
        f"Country / currency: {project.get('country')} / {project.get('currency')}",
        f"Location: {project.get('location')}",
        f"Promoter: {project.get('promoter_name')} ({project.get('promoter_experience')})",
        f"Description: {project.get('project_description')}",
        f"Target market: {project.get('target_market')}; customers: {project.get('target_customers')}",
        f"Total project cost: {project.get('project_cost')}",
        f"Own contribution / equity: {project.get('own_contribution')}",
        f"Loan / funding: {project.get('loan_amount')}",
        f"Purpose: {project.get('purpose')}",
    ]
    if answers:
        lines.append("Questionnaire answers: " + json.dumps(answers))
    return "\n".join(str(x) for x in lines)


def _fields_for_prompt(schema: dict):
    """Flatten the schema into (key, label, type, sample_example, hint) tuples."""
    out = []
    for g in schema.get("groups", []):
        sheet = g["sheet"]
        for f in g.get("fields", []):
            out.append((
                field_key(sheet, f["cell"]),
                f.get("label", ""),
                f.get("type", "number"),
                f.get("default"),
                f.get("hint", ""),
            ))
    return out


def _prompt(project: dict, agent_context: str, fields, currency: str,
            constraints: str = "") -> str:
    field_lines = []
    for key, label, ftype, sample, hint in fields:
        if ftype == "percent":
            unit = "decimal fraction e.g. 0.15 for 15%"
        elif ftype == "text":
            unit = "short free text"
        else:
            unit = ftype
        ctx = f" | basis: {hint}" if hint else ""
        field_lines.append(
            f'- "{key}" | {label} | unit: {unit}{ctx} | sample_example(DO NOT REUSE): {sample}')

    return f"""You are a senior Chartered Accountant and financial modeller building the input assumptions for a client's project financial model.

CLIENT BUSINESS (use ALL of this):
{_project_summary(project)}

SUPPORTING ANALYSIS (context; do not contradict):
{(agent_context or '')[:2500]}

Below is the list of INPUT cells of a professional financial-model template. Each line shows a stable key, a human label, the expected unit, and a sample_example value from an UNRELATED sample business. The sample_example shows ONLY the format/scale/units — it is from a different business and you must NEVER reuse it.

Produce a realistic, internally-consistent value for EVERY key, computed for the CLIENT'S business described above. Base values on the client's stated numbers where given (cost, capacity, prices, financing, tax, growth, etc.), and estimate sensible industry-appropriate figures for anything not stated. Use the "basis" note on each cell to keep values in a realistic band. Monetary values are in {currency}. Percentages MUST be decimal fractions (0.15, not 15). Years/counts are plain integers. "short free text" cells take a brief string (e.g. the unit's name or plant location).
{("MODEL CONSISTENCY REQUIREMENTS (obey exactly): " + constraints) if constraints else ""}

INPUT CELLS:
{chr(10).join(field_lines)}

Return ONLY a single JSON object mapping each key to its value, nothing else:
{{ "Sheet!Cell": <number or short string>, ... }}
Rules:
- Include every key listed above.
- Numeric cells are plain numbers (no currency symbols, commas or text); free-text cells are short strings.
- Never output the sample_example values; compute for the client's business.
- Keep the model consistent (e.g. financing = equity + loan ≈ project cost; margins realistic for the industry; a capacity-utilisation ramp that starts low and rises)."""


def _generate_chunk(project, agent_context, fields, currency, constraints="") -> dict:
    raw = invoke_llm(_prompt(project, agent_context, fields, currency, constraints))
    data = _extract_json(raw)
    types = {k: ftype for (k, _, ftype, _, _) in fields}
    out = {}
    for k, v in (data or {}).items():
        ftype = types.get(k)
        if ftype is None:
            continue
        if ftype == "text":
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
    return out


def _fmt_kpi(val, ftype: str) -> str:
    if ftype == "percent":
        return f"{val * 100:.1f}%"
    if isinstance(val, (int, float)) and float(val).is_integer():
        return f"{val:,.0f}"
    return f"{val:,.2f}"


def derive_headline_kpis(schema: dict, answers: dict) -> list:
    """Headline KPIs computed DIRECTLY from the template's input cells, so the Word
    report can never quote a figure that disagrees with the (editable) Excel model.
    Only exact, input-derived numbers are shown here; genuinely template-computed
    metrics (DSCR, IRR) are surfaced as a pointer to the recomputed Excel sheets."""
    out = []
    for sp in schema.get("headline_kpis", []) or []:
        label = sp.get("label", "")
        ftype = sp.get("type", "number")
        if "ref" in sp:
            out.append({"label": label, "value": sp["ref"]})
        elif "cell" in sp:
            v = answers.get(sp["cell"])
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append({"label": label, "value": _fmt_kpi(v, ftype)})
        elif "sum" in sp:
            vals = [answers.get(c) for c in sp["sum"]]
            vals = [x for x in vals if isinstance(x, (int, float)) and not isinstance(x, bool)]
            if vals:
                out.append({"label": label, "value": _fmt_kpi(sum(vals), ftype)})
        elif "ratio" in sp:
            a, b = answers.get(sp["ratio"][0]), answers.get(sp["ratio"][1])
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b:
                out.append({"label": label, "value": f"{a / b:.2f} : 1"})
    return out


def generate_template_inputs(project: dict, purpose_key: str, template_id: str,
                             agent_context: str = "") -> dict:
    """Return {"Sheet!Cell": value} for every input cell of the template, computed
    for the user's business. Returns {} if the template has no schema."""
    schema = load_schema(purpose_key, template_id)
    if not schema:
        logger.warning("no schema for %s/%s; cannot AI-generate inputs", purpose_key, template_id)
        return {}

    fields = _fields_for_prompt(schema)
    currency = project.get("currency") or "INR"
    constraints = schema.get("constraints", "")
    result = {}
    # Chunk large templates so each request stays within a reliable size.
    for i in range(0, len(fields), _MAX_FIELDS_PER_CALL):
        chunk = fields[i:i + _MAX_FIELDS_PER_CALL]
        try:
            result.update(_generate_chunk(project, agent_context, chunk, currency, constraints))
        except Exception as e:
            logger.warning("AI input generation failed for chunk %d: %s", i, e)
    logger.info("AI generated %d/%d input values for %s/%s",
                len(result), len(fields), purpose_key, template_id)
    return result
