"""
financial_model_service.py

Builds a purpose-specific prompt that instructs the LLM to act as a Chartered
Accountant and return a STRICT JSON financial model (no narrative prose outside
the JSON). The backend then turns that JSON into Word + Excel.

This does NOT add a new agent — it composes the existing agents' output
(market / feasibility / swot) plus the questionnaire answers into one
structured-output call.
"""

import json
from services.claude_service import invoke_llm
from purpose_config import get_config


def _required_headers(config) -> dict:
    """For each sheet, collect the column headers the dashboard charts need so
    the AI is told to include them."""
    needed = {}
    for ch in config.get("charts", []):
        sheet = ch["sheet"]
        cols = needed.setdefault(sheet, set())
        cols.add(ch["x"])
        for s in ch["series"]:
            cols.add(s)
    return {k: sorted(v) for k, v in needed.items()}


def build_prompt(project: dict, purpose_key: str, agent_context: str,
                 sample_blueprint: str = "") -> str:
    config = get_config(purpose_key)
    needed = _required_headers(config)

    sample_block = ""
    if sample_blueprint:
        sample_block = f"""
SAMPLE REPORT BLUEPRINT — this is the reference template for this PURPOSE. Treat it as the blueprint for structure, sheet organisation, column names, layout, number formats and calculation logic. Reproduce the SAME structure and presentation, but:
- Use ONLY the user's data above; NEVER copy the sample's actual values.
- Recompute every figure from the user's inputs, consistent with the sample's methodology.
- Where the user hasn't supplied a value, infer a realistic one consistent with their business and note it as an assumption.
- Your "sheets" output should mirror the sample's sheets, columns and row structure (same names/order where sensible).

{sample_blueprint}
"""

    sheet_specs = []
    for s in config["excel_sheets"]:
        req = needed.get(s["name"])
        line = f'- "{s["name"]}": {s["purpose"]}'
        if req:
            line += f'  [MUST include these exact column headers so charts work: {req}]'
        sheet_specs.append(line)

    section_specs = [f'- "{w["title"]}": {w["guidance"]}' for w in config["word_sections"]]
    answers = project.get("purpose_answers") or {}

    currency = project.get("currency") or "INR"

    return f"""You are a senior Chartered Accountant and financial modeller. You do NOT use a fixed template — you first consider the REPORT PURPOSE below, decide the correct financial-modelling methodology and reporting standard for it, and then produce the model.

REPORT PURPOSE: {config['label']}
INDUSTRY: {project.get('industry') or 'N/A'}  (sub: {project.get('sub_industry') or 'N/A'})
COUNTRY / CURRENCY: {project.get('country') or 'N/A'} / {currency}
BUSINESS: {project.get('title') or 'N/A'}
PROMOTER: {project.get('promoter_name') or 'N/A'} — {project.get('promoter_experience') or 'N/A'}
DESCRIPTION: {project.get('project_description') or 'N/A'}
TARGET MARKET: {project.get('target_market') or 'N/A'}
HEADLINE FINANCES: project_cost={project.get('project_cost')}, own_contribution={project.get('own_contribution')}, loan={project.get('loan_amount')}

PURPOSE-SPECIFIC ANSWERS (use these as the primary numeric inputs; infer reasonable values for anything missing and state assumptions):
{json.dumps(answers, indent=2)}

SUPPORTING ANALYSIS FROM PRIOR AGENTS (use for narrative, do not contradict):
{agent_context[:4000]}
{sample_block}
Produce a complete, internally-consistent model. All monetary values are PLAIN NUMBERS in {currency} (no commas, no symbols, no text). Use realistic CA-grade figures derived from the inputs. Projections cover the standard horizon for this purpose (typically 5 years; for CMA use 2 past + 3 projected).

Return ONLY a single JSON object (no markdown, no commentary) with EXACTLY this shape:

{{
  "narrative": {{
{chr(10).join(f'      "{w["title"]}": "<2-4 short paragraphs of professional prose; use \\n for line breaks; bullet lines may start with - >," ' for w in config["word_sections"])}
  }},
  "kpis": [ {{ "label": "e.g. IRR / DSCR / Break-even", "value": "e.g. 18.4% / 1.85 / 62%" }} ],
  "sheets": [
     {{ "name": "<sheet name>", "columns": ["<header>", ...], "rows": [ ["<cell>", 123, ...], ... ], "total_row": false }}
  ]
}}

The "sheets" array MUST contain exactly these sheets, in this order, each with sensible columns and fully populated numeric rows:
{chr(10).join(sheet_specs)}

The "narrative" object MUST contain exactly these keys:
{chr(10).join(section_specs)}

Rules:
- Numbers are numbers, not strings. The first column of a sheet is a label (string); other columns are numeric where applicable.
- Keep each sheet to the rows that matter (typically 4-15 rows). Include a final "Total" row where it makes accounting sense and set "total_row": true for that sheet.
- Do NOT put large financial tables inside the narrative — tables belong in "sheets".
- Ensure the column headers required for charts (noted above) appear verbatim.
- Output must be valid JSON and nothing else."""


def _extract_json(text: str) -> dict:
    """Pull the first complete JSON object out of the model's response."""
    if not text:
        raise ValueError("Empty model response")
    t = text.strip()
    # strip ``` fences
    if "```" in t:
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
        if m:
            t = m.group(1).strip()
    # narrow to outermost braces
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return json.loads(t[start:end + 1])


def generate_financial_model(project: dict, purpose_key: str, agent_context: str = "",
                             model: str = "claude_sonnet_4_6", sample_blueprint: str = "") -> dict:
    """Return the parsed structured model dict. Raises ValueError on bad output."""
    prompt = build_prompt(project, purpose_key, agent_context, sample_blueprint)
    raw = invoke_llm(prompt, model=model)
    data = _extract_json(raw)

    # Minimal shape guarantees so downstream builders never crash.
    data.setdefault("narrative", {})
    data.setdefault("kpis", [])
    data.setdefault("sheets", [])
    # Drop malformed sheets.
    clean = []
    for s in data["sheets"]:
        if isinstance(s, dict) and s.get("name") and isinstance(s.get("columns"), list) and isinstance(s.get("rows"), list):
            clean.append(s)
    data["sheets"] = clean
    return data
