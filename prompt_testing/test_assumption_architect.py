"""
STANDALONE isolated test for the Assumption Architect agent.

This does NOT touch your Excel pipeline, your FastAPI routes, or your
financial engine. It only tests: given an industry + purpose + user
details, does the AI produce a good, realistic assumptions JSON?

Run this manually, eyeball the output, tweak the prompt in
prompts/assumption_architect_prompt.md until it looks CA-quality — THEN
wire it into your real pipeline.

Provider: DeepSeek (OpenAI-compatible API), matching the production
backend (services/claude_service.py). It reads DEEPSEEK_API_KEY and
DEEPSEEK_MODEL from the environment.

Usage:
    pip install openai
    # PowerShell:  $env:DEEPSEEK_API_KEY="sk-..."; python test_assumption_architect.py
    # bash:        DEEPSEEK_API_KEY="sk-..." python test_assumption_architect.py
"""

import json
import os
import re
from pathlib import Path

from openai import OpenAI

SCHEMA_PATH = Path(__file__).parent / "schemas" / "assumption_schema.json"
PROMPT_PATH = Path(__file__).parent / "prompts" / "assumption_architect_prompt.md"
LABELS_PATH = Path(__file__).parent / "schemas" / "industry_labels.json"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

# --- DeepSeek provider config (same provider as the production backend) ------
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def load_expected_keys() -> list:
    """Expected response keys = the field keys defined in the schema file.

    The schema is a flat mapping of field_key -> {cell, type, ...}. Any key
    starting with '_' (e.g. '_comment') is metadata, not an expected field.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [key for key in schema if not key.startswith("_")]


def load_industry_labels(industry: str) -> dict:
    """Look up cost-label definitions for the given industry.

    Reads schemas/industry_labels.json and returns the cost1_long,
    cost2_long, and cost3_short definitions for `industry`. If the industry
    string isn't present in the file, prints a warning and falls back to
    generic labels.
    """
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    entry = labels.get(industry)
    if entry is None:
        print(
            f"[warning] Industry '{industry}' not found in industry_labels.json "
            "— falling back to generic cost labels."
        )
        return {
            "cost1_long": "Primary direct cost per unit",
            "cost2_long": "Secondary direct cost per unit",
            "cost3_short": "Overhead cost",
        }
    return {
        "cost1_long": entry.get("cost1_long", "Primary direct cost per unit"),
        "cost2_long": entry.get("cost2_long", "Secondary direct cost per unit"),
        "cost3_short": entry.get("cost3_short", "Overhead cost"),
    }


def next_output_path(industry: str, purpose: str) -> Path:
    """Return the next non-overwriting output path for this industry+purpose.

    base name: "<industry>_<purpose>" (lowercased, spaces -> underscores)
    Scans outputs/ for existing "<base>_NN.json", finds the highest NN, and
    returns "<base>_(NN+1).json" (zero-padded to 2 digits, starting at 01).
    """
    base_name = (
        f"{industry.lower().replace(' ', '_')}_"
        f"{purpose.lower().replace(' ', '_')}"
    )
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    pattern = re.compile(rf"^{re.escape(base_name)}_(\d+)\.json$")
    highest = 0
    for existing in OUTPUTS_DIR.glob(f"{base_name}_*.json"):
        match = pattern.match(existing.name)
        if match:
            highest = max(highest, int(match.group(1)))

    return OUTPUTS_DIR / f"{base_name}_{highest + 1:02d}.json"


def call_assumption_architect(industry: str, purpose: str, user_details: str) -> dict:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set in the environment. "
            "Set it before running, e.g. $env:DEEPSEEK_API_KEY='sk-...'"
        )

    labels = load_industry_labels(industry)
    definitions_block = (
        "\n\nIndustry-specific field definitions (you MUST use these exactly):\n"
        f"- cost1_per_unit_y1 represents: {labels['cost1_long']}\n"
        f"- cost2_per_unit_y1 represents: {labels['cost2_long']}\n"
        f"- factory_overheads_monthly_y1 represents: {labels['cost3_short']}"
    )

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        max_tokens=8192,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Industry: {industry}\n"
                    f"Purpose: {purpose}\n"
                    f"User-provided details: {user_details}"
                    + definitions_block
                ),
            },
        ],
    )

    raw_text = response.choices[0].message.content
    # strip accidental markdown fences just in case
    cleaned = re.sub(r"^```json|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def validate(result: dict, expected_keys: list) -> list:
    problems = []
    for key in expected_keys:
        if key not in result:
            problems.append(f"MISSING KEY: {key}")

    try:
        price = result["selling_price_y1"]
        c1 = result["cost1_per_unit_y1"]
        c2 = result["cost2_per_unit_y1"]
        ov = result["other_variable_cost_y1"]
        if price <= (c1 + c2 + ov):
            problems.append(
                f"NEGATIVE/ZERO MARGIN: selling_price_y1={price} <= "
                f"cost1+cost2+other={c1 + c2 + ov}"
            )
    except (KeyError, TypeError):
        problems.append("Could not check margin — missing/bad numeric fields")

    if len(result.get("capacity_utilisation_y1_y5", [])) != 5:
        problems.append("capacity_utilisation_y1_y5 should have exactly 5 values")

    if len(result.get("monthly_seasonality_weights", [])) != 12:
        problems.append("monthly_seasonality_weights should have exactly 12 values")

    return problems


if __name__ == "__main__":
    # ---- EDIT THESE TO TEST DIFFERENT SCENARIOS ----
    industry = "Manufacturing"
    purpose = "Bank Loan"
    user_details = """
    We manufacture plastic packaging containers for FMCG companies. Single
    injection-molding unit, 3 machines. Loan amount needed: 60,00,000 INR
    for a 4th machine to increase capacity.
    """
    # ------------------------------------------------

    print(f"\nTesting: {industry} / {purpose}\n" + "=" * 50)

    expected_keys = load_expected_keys()
    result = call_assumption_architect(industry, purpose, user_details)

    print(json.dumps(result, indent=2))

    # Validate BEFORE saving; the JSON is saved regardless (warnings only).
    problems = validate(result, expected_keys)

    output_path = next_output_path(industry, purpose)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 50)
    print(f"Saved output -> {output_path}")

    print("\n" + "=" * 50)
    if problems:
        print("VALIDATION ISSUES:")
        for problem in problems:
            print(" -", problem)
    else:
        print("Validation passed.")
