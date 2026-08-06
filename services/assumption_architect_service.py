"""
assumption_architect_service.py

Production entry point for the Assumption Architect: given an industry, a report
purpose and the user's free-form details, ask the LLM for a complete set of
financial-model assumptions and return them as a plain dict.

The prompt and the field schema are the ones proven in prompt_testing/ (15/15
schema-complete outputs across 5 industries), read from disk at call time so the
prompt can be tuned there without a code change here.

This service ONLY returns the assumptions dict. It writes no files, builds no
Excel, and touches no existing workflow — wiring it into the generation pipeline
is a separate, later step.
"""

import json
import logging
import re
from pathlib import Path

from services.claude_service import client
from financial_engine.industry_calc.operating_models import get_operating_model, family_of

logger = logging.getLogger("assumption_architect")

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROMPT_TESTING_DIR = BACKEND_DIR / "prompt_testing"

PROMPT_PATH = PROMPT_TESTING_DIR / "prompts" / "assumption_architect_prompt.md"
SCHEMA_PATH = PROMPT_TESTING_DIR / "schemas" / "assumption_schema.json"
LABELS_PATH = PROMPT_TESTING_DIR / "schemas" / "industry_labels.json"
EXTENSIONS_PATH = PROMPT_TESTING_DIR / "schemas" / "purpose_field_extensions.json"

MODEL = "deepseek-chat"
MAX_TOKENS = 8192
TEMPERATURE = 0.4

_GENERIC_LABELS = {
    "cost1_long": "Primary direct cost per unit",
    "cost2_long": "Secondary direct cost per unit",
    "cost3_short": "Overhead cost",
}

# Fields that belong ONLY to the capacity (manufacturing-style) operating model.
# Removed from the schema for volume_price industries (Retail, Restaurant, Hotel,
# Software, Hospital, Education, Trading, Transport, Media, Other) and replaced by
# the "_volume_price_fields" block from assumption_schema.json.
_CAPACITY_ONLY_KEYS = (
    "installed_capacity", "capacity_utilisation_y1_y5",
    "cost1_per_unit_y1", "cost1_escalation",
    "cost2_per_unit_y1", "cost2_escalation",
    "factory_overheads_monthly_y1", "factory_oh_escalation",
)


def load_prompt() -> str:
    """The Assumption Architect system prompt (markdown)."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def load_schema() -> dict:
    """The flat field schema: field_key -> {cell, type, ...}. Keys starting with
    '_' are metadata, not fields."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_for_industry(industry: str) -> dict:
    """The field schema for this industry's operating-model family.

    'capacity' family (Manufacturing and similar) -> the base schema, unchanged.
    'volume_price' family (Retail, Restaurant, Hotel, etc.) -> the base schema with
    the capacity-only fields removed and replaced by the '_volume_price_fields'
    block, so the AI is asked for units-sold/price/margin instead of
    capacity/cost-per-unit.
    """
    base = load_schema()
    if family_of(industry) != "volume_price":
        return {k: v for k, v in base.items() if not k.startswith("_")}
    vp_fields = base.get("_volume_price_fields") or {}
    schema = {k: v for k, v in base.items()
              if not k.startswith("_") and k not in _CAPACITY_ONLY_KEYS}
    schema.update(vp_fields)
    return schema


def expected_keys(schema: dict = None) -> list:
    schema = schema if schema is not None else load_schema()
    return [k for k in schema if not k.startswith("_")]


# ── purpose extensions ─────────────────────────────────────────────────────
# The base schema is the floor for EVERY purpose. A purpose may add fields on top
# of it (a VC deck needs equity/exit terms a bank CMA does not), but the base is
# never duplicated and never modified. Bank Loan declares no extensions, so its
# schema, prompt and output are bit-for-bit what they were before this existed.

def load_extensions() -> dict:
    """purpose_field_extensions.json. A missing/malformed file degrades to 'no
    extensions anywhere', which is exactly the pre-extension behaviour."""
    try:
        return json.loads(EXTENSIONS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError) as e:
        logger.warning("could not read purpose_field_extensions.json (%s); "
                       "falling back to base schema only", e)
        return {}


def _canonical_purpose(purpose: str, extensions: dict) -> str:
    """Map whatever the caller passed ('Bank Loan', 'bank_loan', 'cma_data',
    'venture capital') onto a purpose key in the extensions file. Returns '' if
    unrecognised — an unknown purpose simply gets the base schema."""
    raw = (purpose or "").strip()
    if not raw:
        return ""
    if raw in extensions and not raw.startswith("_"):
        return raw
    slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    alias = (extensions.get("_aliases") or {}).get(slug)
    if alias in extensions:
        return alias
    for key in extensions:
        if key.startswith("_"):
            continue
        if re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_") == slug:
            return key
    return ""


def purpose_fields(purpose: str) -> list:
    """The EXTRA fields this purpose needs beyond the base schema. [] for Bank Loan,
    for an unknown purpose, or when the extensions file is unreadable."""
    extensions = load_extensions()
    key = _canonical_purpose(purpose, extensions)
    if not key:
        if purpose:
            logger.info("no purpose extension entry for %r; using base schema only", purpose)
        return []
    return list((extensions.get(key) or {}).get("additional_fields") or [])


def merged_schema(purpose: str) -> dict:
    """Base schema + this purpose's extension fields, as one flat field map.
    Kept for backward compatibility with any other caller that only cares about
    purpose, not industry. Prefer schema_for_industry() + purpose merge for the
    assumption architect itself (see generate_assumptions)."""
    base = load_schema()
    schema = {k: v for k, v in base.items() if not k.startswith("_")}
    for f in purpose_fields(purpose):
        key = f.get("key")
        if not key or key in base:
            if key in base:
                logger.warning("purpose %r redefines base field %r — base wins, extension ignored",
                               purpose, key)
            continue
        schema[key] = {k: v for k, v in f.items() if k != "key"}
    return schema


def _purpose_block(fields: list, purpose: str) -> str:
    """The extra instruction block appended to the user message for a purpose that
    has extension fields. Returns '' when there are none, so a purpose without
    extensions (Bank Loan) produces a byte-identical prompt to before."""
    if not fields:
        return ""
    lines = [
        f"\n\nADDITIONAL FIELDS REQUIRED FOR THIS PURPOSE ({purpose}) — include EVERY one of "
        "these in the same JSON object, in ADDITION to (never instead of) the base fields:"
    ]
    for f in fields:
        unit = f" [{f['unit']}]" if f.get("unit") else ""
        lines.append(f"- {f['key']} ({f.get('type', 'number')}{unit}): {f.get('description', '')}")
    lines.append(
        "Percentage-type fields among the above follow the same rule as the base schema: "
        "decimal fractions, not whole numbers (0.15, not 15)."
    )
    return "\n".join(lines)


def _industry_labels(industry: str) -> dict:
    """Per-industry meaning of the three capacity-model cost fields. An unknown
    industry falls back to generic labels rather than failing. Only used for the
    'capacity' family — volume_price industries use operating_models.py labels
    instead (see _user_message)."""
    try:
        labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return dict(_GENERIC_LABELS)
    entry = labels.get(industry)
    if not entry:
        logger.warning("industry %r not in industry_labels.json; using generic cost labels", industry)
        return dict(_GENERIC_LABELS)
    return {k: entry.get(k, v) for k, v in _GENERIC_LABELS.items()}


def _user_message(industry: str, purpose: str, user_details: str) -> str:
    if family_of(industry) == "volume_price":
        model = get_operating_model(industry)
        vol_label = model.volume_label if model else "Units sold"
        price_label = model.price_label if model else "Average price per unit"
        cost_label = model.cost_label if model else "Cost of sales"
        base = (
            f"Industry: {industry}\n"
            f"Purpose: {purpose}\n"
            f"User-provided details: {user_details}"
            "\n\nIndustry-specific field definitions (you MUST use these exactly):\n"
            f"- units_sold_y1 represents: {vol_label} — Year 1 base value only (a single number)\n"
            f"- units_growth_index_y1_y5 represents: a 5-value growth index for {vol_label} "
            f"across Year 1 to Year 5, where Year 1 = 1.00 (e.g. [1.00, 1.10, 1.21, 1.33, 1.46])\n"
            f"- selling_price_y1 represents: {price_label}\n"
            f"- gross_margin_pct represents: gross margin on sales as a decimal fraction; "
            f"{cost_label} = revenue x (1 - this margin)\n"
            "Do NOT include installed_capacity, capacity_utilisation_y1_y5, "
            "cost1_per_unit_y1, cost1_escalation, cost2_per_unit_y1, cost2_escalation, "
            "factory_overheads_monthly_y1, or factory_oh_escalation for this industry — "
            "they are not used and must be omitted from the JSON."
        )
    else:
        labels = _industry_labels(industry)
        base = (
            f"Industry: {industry}\n"
            f"Purpose: {purpose}\n"
            f"User-provided details: {user_details}"
            "\n\nIndustry-specific field definitions (you MUST use these exactly):\n"
            f"- cost1_per_unit_y1 represents: {labels['cost1_long']}\n"
            f"- cost2_per_unit_y1 represents: {labels['cost2_long']}\n"
            f"- factory_overheads_monthly_y1 represents: {labels['cost3_short']}"
        )

    reminder = (
        "\n\nDo not omit monthly_seasonality_weights — it is REQUIRED. Provide exactly "
        "12 numbers (relative weights for Jan-Dec). Use [1,1,1,1,1,1,1,1,1,1,1,1] for a "
        "flat/non-seasonal business, or a realistic seasonal pattern if the business "
        "details suggest one (e.g. festive/monsoon/tourist-season peaks)."
    )
    # Appends nothing at all when the purpose has no extensions, so Bank Loan's
    # prompt is character-for-character unchanged aside from this reminder, which
    # applies uniformly regardless of purpose.
    return base + _purpose_block(purpose_fields(purpose), purpose) + reminder


def _parse_json(raw: str) -> dict:
    """Model output -> dict, tolerating markdown fences around the JSON."""
    cleaned = re.sub(r"^```json|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def generate_assumptions(industry: str, purpose: str, user_details: str) -> dict:
    """Return the AI-generated assumptions dict for this business.

    The schema is chosen by the industry's operating-model family first (capacity
    vs volume_price — see schema_for_industry), then extended with this purpose's
    extra fields (none for Bank Loan). Completeness is checked against that merged
    schema, so a missing field is surfaced whichever family it came from.

    Raises ValueError if the model's reply is not parseable JSON.
    """
    base_schema = schema_for_industry(industry)
    extra = {
        f["key"]: {k: v for k, v in f.items() if k != "key"}
        for f in purpose_fields(purpose)
        if f.get("key") and f["key"] not in base_schema
    }
    schema = {**base_schema, **extra}

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": load_prompt()},
            {"role": "user", "content": _user_message(industry, purpose, user_details)},
        ],
    )

    raw = response.choices[0].message.content
    try:
        assumptions = _parse_json(raw)
    except ValueError as e:
        logger.error("assumption architect returned unparseable JSON: %s", e)
        raise ValueError(f"Assumption Architect did not return valid JSON: {e}")

    missing = [k for k in expected_keys(schema) if k not in assumptions]
    if missing:
        logger.warning("assumptions missing %d schema field(s): %s", len(missing), missing)
    n_ext = len(purpose_fields(purpose))
    logger.info("assumptions generated for %s/%s: %d fields returned "
                "(%d expected = %d base + %d purpose, %d missing)",
                industry, purpose, len(assumptions), len(expected_keys(schema)) - n_ext,
                n_ext, len(missing))
    return assumptions