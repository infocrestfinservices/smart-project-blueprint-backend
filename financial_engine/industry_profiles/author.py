"""
author.py

Authors an industry profile with AI, then freezes it to JSON for review.

This is a DESIGN-TIME tool, not a request-time path. Report generation never calls
it: generation reads a frozen profile and nothing else. Authoring is deliberate and
rare — run it, read the diff, keep it or regenerate. That separation is what lets
the shape be AI-written yet stable enough for a bank, which will compare two
submissions of the same file and must not find the rows moved.

Run from backend/:
    python -m financial_engine.industry_profiles.author retail
    python -m financial_engine.industry_profiles.author retail --print   # no write
"""

from __future__ import annotations

import datetime
import json
import os
import sys

from services.assumption_architect_service import load_schema
from services.claude_service import invoke_llm
from services.financial_model_service import _extract_json

from .profile import PROFILE_DIR, from_dict, profile_path

# Engine fields that describe the business rather than model it. Every industry
# needs them, so they are not the AI's to reason about.
_IDENTITY_FIELDS = {"name_of_unit", "constitution", "line_of_activity", "industry_type"}


def engine_fields() -> dict:
    """The engine's real assumption vocabulary — read from the production schema so
    a profile can never describe a field the engine does not compute on."""
    return {k: v for k, v in load_schema().items()
            if not k.startswith("_") and k not in _IDENTITY_FIELDS}


def _prompt(industry: str, display_name: str, fields: dict) -> str:
    lines = [f'- "{k}" ({v.get("type", "number") if isinstance(v, dict) else "number"})'
             for k, v in fields.items()]
    return f"""You are a senior Indian Chartered Accountant who prepares bank-grade CMA and project reports. You are describing how the {display_name} industry ACTUALLY works, so a financial model can stop treating every business as a factory.

Below is the fixed vocabulary of a financial engine. It was designed around manufacturing, so some fields genuinely DO NOT APPLY to {display_name}. Saying so is the single most valuable thing you can do here: a model that asks a supermarket for raw-material holding days, or depreciates plant & machinery it does not own, is obviously wrong to any banker.

ENGINE FIELDS:
{chr(10).join(lines)}

For EVERY field above return an object with:
  - "applies": true/false — false when this industry genuinely does not have this
    concept. Be strict and honest. Do not keep a field just because the engine has
    it; do not drop a field the industry really does have.
  - "label": what a {display_name} CA would call this line in a report. Use the
    industry's real vocabulary, not manufacturing's. Omit when applies=false.
  - "band": [low, high] — the plausible range for a typical Indian {display_name}
    business. Percentages are decimal fractions (0.05 = 5%). Money is INR. Omit
    when applies=false or when no meaningful range exists (e.g. an escalation that
    tracks general inflation is still worth a band; a company's own loan amount is
    not).
  - "default": a sensible mid-point benchmark, same units as band. Omit if none.
  - "rationale": one short sentence. When applies=false, say WHY this industry has
    no such concept — this is what a reviewing CA will read.

Also return:
  - "revenue_model": one sentence stating what actually drives revenue in this
    industry (what the units and the price really represent here).
  - "notes": 2-5 short strings — the structural facts about {display_name} that a
    generic model gets wrong. State what is different, not what is generic.

Ground every number in real Indian {display_name} economics. Be specific: a
supermarket's gross margin is nothing like a software firm's, and a band wide
enough to be always true is useless.

Return ONLY this JSON object, nothing else:
{{
  "industry": "{industry}",
  "display_name": "{display_name}",
  "revenue_model": "...",
  "notes": ["..."],
  "fields": {{ "field_key": {{"applies": true, "label": "...", "band": [lo, hi], "default": x, "rationale": "..."}} }}
}}"""


def author_profile(industry: str, display_name: str) -> dict:
    """Ask the AI to describe this industry against the engine's vocabulary."""
    fields = engine_fields()
    data = _extract_json(invoke_llm(_prompt(industry, display_name, fields)))
    if not isinstance(data, dict) or not data.get("fields"):
        raise RuntimeError(f"AI returned no usable profile for {industry}: {str(data)[:200]}")

    # The AI describes; it does not get to invent vocabulary. Anything outside the
    # engine's fields cannot be computed, so it would be a silently dead rule.
    unknown = [k for k in data["fields"] if k not in fields]
    missing = [k for k in fields if k not in data["fields"]]
    for k in unknown:
        data["fields"].pop(k)
    data["industry"] = industry
    data["display_name"] = display_name
    data["authored_by"] = "deepseek-chat"
    data["frozen_at"] = datetime.datetime.now().strftime("%Y-%m-%d")
    data["_coverage"] = {"described": len(data["fields"]), "of": len(fields),
                         "unknown_dropped": unknown, "not_described": missing}
    return data


def freeze(data: dict) -> str:
    """Write the profile to disk. Explicit and reviewable — never called at request time."""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    p = profile_path(data["industry"])
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return p


def main(argv) -> int:
    if not argv:
        print(__doc__)
        return 2
    industry = argv[0]
    display = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else industry
    data = author_profile(industry, display)
    prof = from_dict(data)          # prove it parses back into the contract
    cov = data["_coverage"]
    print(f"authored {industry} ({display}) by {data['authored_by']}")
    print(f"  described {cov['described']}/{cov['of']} engine fields")
    if cov["not_described"]:
        print(f"  NOT described: {cov['not_described']}")
    if cov["unknown_dropped"]:
        print(f"  dropped (not engine fields): {cov['unknown_dropped']}")
    print(f"  does NOT apply to this industry ({len(prof.excluded())}): {prof.excluded()}")
    if "--print" in argv:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print(f"  frozen -> {freeze(data)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
