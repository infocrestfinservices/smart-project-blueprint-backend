"""
template_config.py

Registry of the concrete sample workbooks ("templates") shipped for each purpose.
A purpose can offer several templates; the user picks one and we generate a report
that mirrors that exact workbook (see services/template_fill_service.py).

Each template maps to a file under backend/samples/<purpose_key>/ and, once its
input schema has been extracted + curated, a sibling <template_id>.schema.json
that defines the questions we ask the user.

Keys line up with purpose_config.py. CMA is intentionally left as engine="deferred"
(its inputs are financial statements, handled on a later upload track).
"""

import json
import os

from purpose_config import (  # noqa: F401 (re-exported for callers)
    FEASIBILITY, CMA, IRR, GENERIC, IMMIGRATION, REAL_ESTATE, STARTUP,
)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BACKEND_DIR, "samples")

# Templates uploaded at runtime live under templates/uploaded/<id>/ and are recorded
# in this JSON overlay, so new templates can be added without touching this file.
TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
UPLOAD_DIR = os.path.join(TEMPLATES_DIR, "uploaded")
REGISTRY_FILE = os.path.join(TEMPLATES_DIR, "_registry.json")

# engine:
#   "template_fill" -> open the workbook, overwrite input cells, let Excel recompute
#   "deferred"      -> not wired yet (CMA statement-upload track)
# Only real, present templates are registered here. Templates marked
# "universal": True are offered under EVERY purpose (see list_templates); the
# original sample workbooks (chewing-gum, sulphuric-acid, germany, condo, hotel,
# solar, apple-chips, beer, …) were removed and are intentionally not registered.
TEMPLATES = {
    CMA: [
        {
            # The shipped bank-loan CMA workbook, genericised to neutral
            # manufacturing wording (12 cross-linked sheets: Assumptions ->
            # Project Cost -> Term Loan -> Depreciation -> Monthly Model ->
            # Form II/III/VI, Form IV-V (WC & MPBF), Ratios & DSCR, Investor
            # Dashboard). Every sheet but the blue input cells is a live formula,
            # so filling the inputs recomputes the entire model in Excel.
            "id": "bank_loan_cma",
            "label": "CMA Report — Bank Term Loan (All Industries)",
            "file": "CMA_Dashboard_Premium.xlsx",
            "currency": "INR",
            "engine": "template_fill",
            # Offered under every purpose, not just CMA.
            "universal": True,
            # This workbook ships under backend/templates/bank_loan/ rather than
            # the samples/<purpose_key>/ convention, so point at it explicitly.
            "root": "templates",
            "folder": "bank_loan",
        },
    ],
}


def _template_file_exists(purpose_key: str, t: dict) -> bool:
    return os.path.isfile(os.path.join(_template_dir(purpose_key, t), t["file"]))


def _load_registry() -> dict:
    """User-uploaded templates recorded in templates/_registry.json, grouped by
    purpose. Read fresh on every call so a template uploaded at runtime is offered
    immediately, with no server restart. Malformed/missing file -> no dynamic
    templates (built-ins still work)."""
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return {}
    out = {}
    for entry in data.get("templates", []):
        pk = entry.get("purpose") or CMA
        out.setdefault(pk, []).append(entry)
    return out


def _merged_templates() -> dict:
    """Built-in TEMPLATES + dynamic (uploaded) templates, keyed by purpose."""
    merged = {pk: list(v) for pk, v in TEMPLATES.items()}
    for pk, entries in _load_registry().items():
        merged.setdefault(pk, []).extend(entries)
    return merged


def list_templates(purpose_key: str, include_missing: bool = False):
    """Templates offered for a purpose. This is the purpose's own templates (built-in
    + uploaded) PLUS any template flagged "universal" (offered under every purpose).
    By default only templates whose workbook actually exists on disk are returned, so
    deleting a template file removes it from the picker automatically and dropping /
    uploading a new one makes it appear — no phantom entries, no code changes."""
    allt = _merged_templates()
    own = list(allt.get(purpose_key, []))
    own_ids = {t["id"] for t in own}
    universal, seen = [], set()
    for entries in allt.values():
        for t in entries:
            if t.get("universal") and t["id"] not in own_ids and t["id"] not in seen:
                seen.add(t["id"])
                universal.append(t)
    merged = own + universal
    if include_missing:
        return merged
    return [t for t in merged if _template_file_exists(purpose_key, t)]


def get_template(purpose_key: str, template_id: str):
    for t in list_templates(purpose_key, include_missing=True):
        if t["id"] == template_id:
            return t
    # A dynamic/universal template registered under another purpose is still valid.
    _, t = find_template_by_id(template_id)
    return t


def find_template_by_id(template_id: str):
    """Template ids are globally unique, so a chosen template can be located
    without knowing its purpose. Consults built-in + uploaded templates.
    Returns (purpose_key, template) or (None, None)."""
    if not template_id:
        return None, None
    for purpose_key, templates in _merged_templates().items():
        for t in templates:
            if t["id"] == template_id:
                return purpose_key, t
    return None, None


def add_dynamic_template(entry: dict) -> None:
    """Append (or replace by id) an uploaded template in templates/_registry.json."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        data = {}
    templates = [t for t in data.get("templates", []) if t.get("id") != entry["id"]]
    templates.append(entry)
    data["templates"] = templates
    with open(REGISTRY_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def remove_dynamic_template(template_id: str) -> bool:
    """Remove an uploaded template from the registry. Returns True if it existed.
    (Only dynamic templates can be removed; built-ins live in code.)"""
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        return False
    before = data.get("templates", [])
    after = [t for t in before if t.get("id") != template_id]
    if len(after) == len(before):
        return False
    data["templates"] = after
    with open(REGISTRY_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return True


def is_dynamic_template(template_id: str) -> bool:
    return any(t.get("id") == template_id
              for entries in _load_registry().values() for t in entries)


def default_template(purpose_key: str):
    """First template-fill template for a purpose, or None."""
    for t in list_templates(purpose_key):
        if t.get("engine") == "template_fill":
            return t
    return None


def _template_dir(purpose_key: str, t: dict) -> str:
    """Directory holding a template's workbook + schema. Defaults to the
    samples/<purpose_key>/ convention, but a template may override it with
    `root` (relative to backend/) and `folder` — e.g. the shipped bank-loan
    workbook lives under templates/bank_loan/."""
    root = t.get("root")
    if root:
        return os.path.join(BACKEND_DIR, root, t.get("folder", purpose_key))
    return os.path.join(SAMPLES_DIR, purpose_key)


def template_path(purpose_key: str, template_id: str):
    t = get_template(purpose_key, template_id)
    if not t:
        return None
    path = os.path.join(_template_dir(purpose_key, t), t["file"])
    return path if os.path.isfile(path) else None


def schema_path(purpose_key: str, template_id: str):
    """Path to the curated input-schema JSON for a template (may not exist yet)."""
    t = get_template(purpose_key, template_id)
    folder = _template_dir(purpose_key, t) if t else os.path.join(SAMPLES_DIR, purpose_key)
    return os.path.join(folder, f"{template_id}.schema.json")


def analysis_path(purpose_key: str, template_id: str):
    """Path to the KPI/consistency-check mapping JSON for a template (auto-generated
    at upload; hand-editable to precisely wire any template)."""
    t = get_template(purpose_key, template_id)
    folder = _template_dir(purpose_key, t) if t else os.path.join(SAMPLES_DIR, purpose_key)
    return os.path.join(folder, f"{template_id}.analysis.json")
