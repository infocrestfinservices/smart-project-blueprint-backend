"""
profile.py

An INDUSTRY PROFILE: the description of how one industry actually behaves,
expressed against the engine's own 44-field assumption vocabulary.

WHY THIS EXISTS
---------------
Until now "industry" was cosmetic. The live workbook's INDUSTRY_MAP holds eight
columns and every one of them is a LABEL — no formula anywhere pulls a number from
it. So a software firm and a farm were the same model wearing different words:
both "Installed Capacity x Utilisation x Price", both asked for raw-material
holding days, both depreciated plant & machinery. A CA reads through that in
seconds.

A profile makes the difference structural instead of cosmetic. For each engine
field it states whether the field APPLIES to this industry at all, what it is
CALLED here, and the BAND a plausible value falls in. A retailer's profile
switches raw_material_holding_days off entirely (there is no raw-material stage
when you buy finished goods) rather than labelling it something friendlier.

WHY THE SHAPE IS FROZEN DATA, NOT CODE
--------------------------------------
The shape is authored by AI (see author.py) and then frozen to JSON and reviewed.
Two runs for the same industry must produce the same structure: a bank comparing
two submissions of the same file must not see the rows move. Authoring is an
explicit, reviewable act; generation only ever reads a frozen profile.

Profiles are data, so industry #18 is a reviewed JSON file — not a new Python
class. This implements the existing BaseIndustryModel contract rather than
replacing it: ProfileBackedIndustryModel is one class serving every industry.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

PROFILE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class FieldRule:
    """How one engine field behaves in this industry.

    `applies=False` is the structurally important case: the field is not part of
    this industry's model, so the engine must see 0/absent and the writer must not
    show the row. `band` is a plausibility range (lo, hi) used to catch an AI value
    that is not wrong arithmetic but is wrong for the industry.
    """
    key: str
    applies: bool = True
    label: str = ""
    band: Optional[Tuple[float, float]] = None
    default: Optional[float] = None
    rationale: str = ""

    def in_band(self, value) -> bool:
        if self.band is None or not isinstance(value, (int, float)):
            return True
        lo, hi = self.band
        return lo <= value <= hi


@dataclass(frozen=True)
class IndustryProfile:
    """One industry's frozen shape."""
    industry: str
    display_name: str
    revenue_model: str = ""
    rules: Dict[str, FieldRule] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    authored_by: str = ""
    frozen_at: str = ""

    # -- queries ------------------------------------------------------------
    def rule(self, key: str) -> FieldRule:
        return self.rules.get(key) or FieldRule(key=key)

    def applies(self, key: str) -> bool:
        return self.rule(key).applies

    def label(self, key: str) -> str:
        return self.rule(key).label or key

    def excluded(self) -> List[str]:
        """Fields this industry does not model at all — the structural difference."""
        return sorted(k for k, r in self.rules.items() if not r.applies)

    def out_of_band(self, assumptions: dict) -> List[str]:
        """Fields whose value is arithmetically fine but implausible for this
        industry (e.g. a 60% gross margin on a supermarket)."""
        out = []
        for k, v in (assumptions or {}).items():
            r = self.rules.get(k)
            if r and r.applies and not r.in_band(v):
                out.append(f"{k}={v!r} outside {r.band} for {self.display_name}")
        return out


def _to_rule(key: str, d: dict) -> FieldRule:
    band = d.get("band")
    if isinstance(band, (list, tuple)) and len(band) == 2:
        band = (float(band[0]), float(band[1]))
    else:
        band = None
    return FieldRule(
        key=key,
        applies=bool(d.get("applies", True)),
        label=str(d.get("label") or ""),
        band=band,
        default=d.get("default"),
        rationale=str(d.get("rationale") or ""),
    )


def from_dict(data: dict) -> IndustryProfile:
    return IndustryProfile(
        industry=data["industry"],
        display_name=data.get("display_name", data["industry"]),
        revenue_model=data.get("revenue_model", ""),
        rules={k: _to_rule(k, v) for k, v in (data.get("fields") or {}).items()},
        notes=list(data.get("notes") or []),
        authored_by=data.get("authored_by", ""),
        frozen_at=data.get("frozen_at", ""),
    )


def profile_path(industry: str) -> str:
    return os.path.join(PROFILE_DIR, f"{industry}.json")


def load_profile(industry: str) -> Optional[IndustryProfile]:
    """The frozen profile for an industry, or None if one has not been authored."""
    p = profile_path(industry)
    if not os.path.isfile(p):
        return None
    with open(p, "r", encoding="utf-8") as fh:
        return from_dict(json.load(fh))


def available() -> List[str]:
    return sorted(
        f[:-5] for f in os.listdir(PROFILE_DIR)
        if f.endswith(".json") and not f.startswith("_")
    )
