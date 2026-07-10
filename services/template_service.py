"""
template_service.py

Template management for purpose-based report generation.

Maps a numeric purpose id (as selected by the user) to its blank report template
(`report_template.docx`) under `backend/templates/<purpose>/`, and loads it for
downstream processing.

Intended flow (implemented elsewhere, not here):
    user selects purpose -> load_template() -> AI reads the report structure ->
    AI asks dynamic questions -> user answers -> AI fills the template ->
    final DOCX generated.

This module is template plumbing ONLY — no AI generation, no financial
calculations, no content generation.
"""

import os
from typing import Dict

# purpose_id -> template folder name (canonical template name)
PURPOSE_TEMPLATES: Dict[int, str] = {
    1: "bank_loan",
    2: "feasibility_study",
    3: "government_grant",
    4: "venture_capital",
    5: "angel_investment",
    6: "immigration_business_plan",
    7: "internal_business_planning",
    8: "real_estate",
    9: "startup_sme_fundraising",
}

# Every purpose folder holds a single template file with this fixed name.
TEMPLATE_FILENAME = "report_template.docx"

# backend/services/template_service.py -> backend/templates/
TEMPLATES_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)


class UnknownPurposeError(ValueError):
    """Raised when a purpose id has no registered template."""


class TemplateNotFoundError(FileNotFoundError):
    """Raised when a purpose's template file is missing on disk."""


def _resolve_folder(purpose_id) -> str:
    """Validate the purpose id and return its template folder name."""
    try:
        pid = int(purpose_id)
    except (TypeError, ValueError):
        raise UnknownPurposeError(f"Invalid purpose id: {purpose_id!r}")
    folder = PURPOSE_TEMPLATES.get(pid)
    if folder is None:
        raise UnknownPurposeError(
            f"No template registered for purpose id {pid}. "
            f"Valid ids: {sorted(PURPOSE_TEMPLATES)}"
        )
    return folder


def get_template_name(purpose_id) -> str:
    """Return the canonical template name for a purpose (e.g. 'bank_loan')."""
    return _resolve_folder(purpose_id)


def get_template_path(purpose_id) -> str:
    """Return the absolute path to a purpose's `report_template.docx`.

    Raises UnknownPurposeError for an unmapped purpose id and
    TemplateNotFoundError if the template file does not exist on disk.
    """
    folder = _resolve_folder(purpose_id)
    path = os.path.join(TEMPLATES_ROOT, folder, TEMPLATE_FILENAME)
    if not os.path.isfile(path):
        raise TemplateNotFoundError(f"Template file not found: {path}")
    return path


def load_template(purpose_id):
    """Load a purpose's DOCX template and return it as a python-docx Document.

    The returned Document is what downstream steps read the report structure
    from (and later fill). This function does not modify the file on disk.
    """
    from docx import Document  # imported lazily so the module loads without python-docx

    return Document(get_template_path(purpose_id))
