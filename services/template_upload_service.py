"""
template_upload_service.py

Turn an uploaded workbook / document into a first-class, ready-to-use template with
NO code changes:

  1. save the file under templates/uploaded/<id>/,
  2. auto-detect its structure — Excel: blue-font input cells (extract_schema);
     Word: {{placeholders}} (docx_fill_service),
  3. generate + write the input schema (the questions the app asks / the AI fills),
  4. register it in templates/_registry.json (add_dynamic_template).

The file itself is stored byte-for-byte, so every formula, chart, table and layout
is preserved — filling only ever writes values into the detected input spots.

Excel templates plug straight into the existing generate/download pipeline
(template_fill). Word templates use the docx_fill engine.
"""

import hashlib
import json
import os
import re

from template_config import (
    UPLOAD_DIR, TEMPLATES_DIR, BACKEND_DIR, CMA,
    add_dynamic_template, find_template_by_id, _merged_templates, _template_dir,
)
from services.template_introspect import extract_schema
from services.docx_fill_service import detect_placeholders
from services.template_analysis import analyze_template

_EXCEL_EXT = (".xlsx", ".xlsm")
_WORD_EXT = (".docx",)
ALLOWED_EXT = _EXCEL_EXT + _WORD_EXT


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s or "template"


def _prettify(name: str) -> str:
    return re.sub(r"[_\-]+", " ", name).strip().capitalize()


# acronyms to keep upper-cased in a prettified template name
_ACRONYMS = {"MSME", "CMA", "VC", "DSCR", "IRR", "NPV", "ROI", "ROE", "ROCE", "ESG",
             "MPBF", "SME", "LLP", "EMI", "GST", "EBITDA", "P&L", "DPR", "TOL", "TNW"}


def _prettify_label(stem: str) -> str:
    """Turn a raw filename stem into a clean picker label, e.g.
    'MSME_Financial_Model_Government Grant_BLANK_TEMPLATE' -> 'MSME Financial Model — Government Grant';
    'CMA_Report_Template' -> 'CMA Report Template'."""
    s = re.sub(r"\s*\(\d+\)\s*$", "", stem)                       # trailing "(3)"
    s = re.sub(r"[_\s]+(BLANK[_\s]+TEMPLATE|BLANK|FINAL)\s*$", "", s, flags=re.I)
    # em-dash before the first multi-word qualifier segment (a scheme/category phrase)
    parts, rebuilt, dashed = s.split("_"), "", False
    for i, p in enumerate(parts):
        if i == 0:
            rebuilt = p
        elif not dashed and " " in p.strip():
            rebuilt += " — " + p
            dashed = True
        else:
            rebuilt += " " + p
    s = re.sub(r"\s+", " ", rebuilt).strip()

    def _case(w):
        if w in ("—", "-", "&"):
            return w
        if w.upper() in _ACRONYMS:
            return w.upper()
        if len(w) > 1 and re.match(r"^[A-Z0-9&]+$", w):   # already an acronym
            return w
        return w[:1].upper() + w[1:] if w else w

    return " ".join(_case(w) for w in s.split(" "))


def _unique_id(base: str, content: bytes) -> str:
    """A stable id: slug + short content hash. Re-uploading the same file yields the
    same id (idempotent overwrite); a different file gets a different id."""
    digest = hashlib.sha1(content).hexdigest()[:8]
    return f"{_slug(base)}_{digest}"


def _write_schema(dir_path: str, template_id: str, schema: dict) -> None:
    with open(os.path.join(dir_path, f"{template_id}.schema.json"), "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)


def _write_analysis(dir_path: str, template_id: str, path: str) -> int:
    """Auto-detect + persist the KPI/consistency mapping for an Excel template.
    Non-fatal: a template that can't be analysed still registers (empty mapping)."""
    try:
        analysis = analyze_template(path)
    except Exception:
        analysis = {"kpis": [], "checks": []}
    with open(os.path.join(dir_path, f"{template_id}.analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(analysis, fh, indent=2, ensure_ascii=False)
    return len(analysis.get("kpis", [])) + len(analysis.get("checks", []))


def _docx_schema(template_id: str, file_name: str, currency: str, names: list) -> dict:
    return {
        "template_id": template_id,
        "file": file_name,
        "currency": currency,
        "truncated": False,
        "groups": [{
            "title": "Document Fields",
            "sheet": "",
            "fields": [
                {"cell": nm, "label": _prettify(nm), "hint": "", "default": None, "type": "text"}
                for nm in names
            ],
        }],
    }


def register_uploaded_template(content: bytes, filename: str, *, label: str = "",
                               purpose: str = "", currency: str = "INR",
                               universal: bool = None) -> dict:
    """Save, introspect, schema-generate and register an uploaded template.

    Returns metadata: {template_id, label, purpose, engine, currency, universal,
    fields, available}. Raises ValueError on an unsupported type or a file we cannot
    introspect."""
    base_name = os.path.basename(filename or "").strip()
    ext = os.path.splitext(base_name)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file type '{ext or '?'}'. Allowed: {', '.join(ALLOWED_EXT)}")
    if not content:
        raise ValueError("Empty file")

    label = (label or "").strip() or _prettify_label(os.path.splitext(base_name)[0])
    template_id = _unique_id(label, content)
    dir_path = os.path.join(UPLOAD_DIR, template_id)
    os.makedirs(dir_path, exist_ok=True)

    # store the file byte-for-byte (safe name, no path traversal)
    safe_name = re.sub(r"[\\/]+", "_", base_name) or f"{template_id}{ext}"
    file_path = os.path.join(dir_path, safe_name)
    with open(file_path, "wb") as fh:
        fh.write(content)

    # introspect + schema
    if ext in _EXCEL_EXT:
        engine = "template_fill"
        try:
            schema = extract_schema(file_path, template_id, currency)
        except Exception as e:
            raise ValueError(f"Could not read the Excel template: {e}")
        fields = sum(len(g["fields"]) for g in schema.get("groups", []))
    else:
        engine = "docx_fill"
        try:
            names = detect_placeholders(file_path)
        except Exception as e:
            raise ValueError(f"Could not read the Word template: {e}")
        schema = _docx_schema(template_id, safe_name, currency, names)
        fields = len(names)

    _write_schema(dir_path, template_id, schema)
    if ext in _EXCEL_EXT:
        _write_analysis(dir_path, template_id, file_path)  # KPI + consistency mapping

    # default: no purpose given -> offered under every purpose
    if universal is None:
        universal = not bool(purpose)
    purpose_key = purpose or CMA

    entry = {
        "id": template_id,
        "label": label,
        "file": safe_name,
        "currency": currency,
        "engine": engine,
        "purpose": purpose_key,
        "universal": bool(universal),
        "root": "templates",
        "folder": os.path.join("uploaded", template_id).replace("\\", "/"),
        "uploaded": True,
    }
    add_dynamic_template(entry)

    return {
        "template_id": template_id,
        "label": label,
        "purpose": purpose_key,
        "engine": engine,
        "currency": currency,
        "universal": bool(universal),
        "fields": fields,
        "available": True,
    }


def _introspect(path: str, template_id: str, currency: str):
    """(engine, schema, field_count) for a file already on disk."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _EXCEL_EXT:
        schema = extract_schema(path, template_id, currency)
        return "template_fill", schema, sum(len(g["fields"]) for g in schema.get("groups", []))
    names = detect_placeholders(path)
    return "docx_fill", _docx_schema(template_id, os.path.basename(path), currency, names), len(names)


def register_existing_template(path: str, *, label: str = "", purpose: str = "",
                               currency: str = "INR", universal: bool = None,
                               require_fields: bool = False) -> dict:
    """Register a template file that already lives on disk, IN PLACE (no copy) — e.g.
    a workbook dropped into templates/<category>/. Its schema is written beside it.
    With require_fields=True, a file with no detected inputs is rejected (raised)
    rather than registered — used by the folder scan to ignore non-fill documents."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file type '{ext or '?'}'")
    with open(path, "rb") as fh:
        content = fh.read()
    label = (label or "").strip() or _prettify_label(os.path.splitext(os.path.basename(path))[0])
    template_id = _unique_id(label, content)

    rel = os.path.relpath(path, BACKEND_DIR).replace("\\", "/")
    parts = rel.split("/")               # e.g. templates/angel_investment/Model.xlsx
    root, folder, fname = parts[0], "/".join(parts[1:-1]), parts[-1]

    try:
        engine, schema, fields = _introspect(path, template_id, currency)
    except Exception as e:
        raise ValueError(f"Could not read the template: {e}")
    if require_fields and fields == 0:
        raise ValueError("no input fields detected (not a fill template)")
    _write_schema(os.path.dirname(path), template_id, schema)
    if engine == "template_fill":
        _write_analysis(os.path.dirname(path), template_id, path)  # KPI + consistency mapping

    if universal is None:
        universal = not bool(purpose)
    entry = {
        "id": template_id, "label": label, "file": fname, "currency": currency,
        "engine": engine, "purpose": purpose or CMA, "universal": bool(universal),
        "root": root, "folder": folder, "uploaded": True, "source": "scan",
    }
    add_dynamic_template(entry)
    return {"template_id": template_id, "label": label, "engine": engine,
            "fields": fields, "universal": bool(universal), "file": fname, "folder": folder}


def _registered_paths() -> set:
    """Absolute paths of every workbook a registered template (built-in or dynamic)
    already points at — so a scan never double-registers the same file."""
    out = set()
    for pk, entries in _merged_templates().items():
        for t in entries:
            out.add(os.path.abspath(os.path.join(_template_dir(pk, t), t["file"])))
    return out


def scan_templates_dir(universal: bool = True) -> list:
    """Register every template file under templates/<category>/ that isn't already
    registered (idempotent — content-hash ids + path de-dup). Skips the uploaded/ dir
    and non-template files. Returns metadata for the newly-registered templates."""
    if not os.path.isdir(TEMPLATES_DIR):
        return []
    known = _registered_paths()
    added = []
    for category in sorted(os.listdir(TEMPLATES_DIR)):
        cat_dir = os.path.join(TEMPLATES_DIR, category)
        if not os.path.isdir(cat_dir) or category == "uploaded":
            continue
        for name in sorted(os.listdir(cat_dir)):
            if os.path.splitext(name)[1].lower() not in ALLOWED_EXT:
                continue
            path = os.path.join(cat_dir, name)
            if os.path.abspath(path) in known:
                continue  # already backs a built-in/registered template
            # idempotent for duplicate-content files across folders (same content id)
            with open(path, "rb") as fh:
                tid = _unique_id(os.path.splitext(name)[0], fh.read())
            if find_template_by_id(tid)[1] is not None:
                known.add(os.path.abspath(path))
                continue
            try:
                meta = register_existing_template(path, purpose="", universal=universal,
                                                  require_fields=True)
                meta["category"] = category
                added.append(meta)
                known.add(os.path.abspath(path))
            except ValueError as e:
                added.append({"file": name, "category": category, "skipped": str(e)})
    return added
