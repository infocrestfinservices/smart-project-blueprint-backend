"""
assumption_mapper.py

Bridge between the Assumption Architect's output and the template-fill pipeline.

The AI returns 44 semantic fields ("term_loan_amount": 6000000). The fill engine
(services/template_fill_service.py) speaks "Sheet!Cell" -> value ("Assumptions!C8":
6000000) and understands SINGLE cells only. Two AI fields are arrays mapped to cell
RANGES — capacity_utilisation_y1_y5 (C18:G18) and monthly_seasonality_weights
(C21:N21) — so this module expands them into one key per cell. 44 fields -> 59 cells,
which is exactly the template's 59 blue input cells.

The cell mapping is read from prompt_testing/schemas/assumption_schema.json, so it
stays in one place and the mapping cannot drift from what the prompt was tested
against.

No AI calls, no Excel, no financial arithmetic — this only reshapes keys.
"""

import json
import logging
from pathlib import Path

from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries

logger = logging.getLogger("assumption_mapper")

BACKEND_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BACKEND_DIR / "prompt_testing" / "schemas" / "assumption_schema.json"

# A missing value is left as None on purpose: template_fill_service._coerce() skips
# None/"" so the cell keeps the template's own blank, which Excel evaluates as 0 in
# every downstream formula. Writing a literal 0 would instead assert a real financial
# figure the AI never produced.
_MISSING = None


def load_cell_map() -> dict:
    """field_key -> {"cell": "Sheet!Ref", "type": ...}. '_'-prefixed keys are
    schema metadata, not fields."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in schema.items() if not k.startswith("_")}


def _expand(cell_ref: str):
    """'Assumptions!C8' -> ['Assumptions!C8']
    'Assumptions!C18:G18' -> ['Assumptions!C18', ..., 'Assumptions!G18']
    Row-major, so the order matches the array the AI returns."""
    sheet, ref = cell_ref.split("!", 1)
    if ":" not in ref:
        return [f"{sheet}!{ref}"]
    min_col, min_row, max_col, max_row = range_boundaries(ref)
    return [
        f"{sheet}!{get_column_letter(col)}{row}"
        for row in range(min_row, max_row + 1)
        for col in range(min_col, max_col + 1)
    ]


def _fill_range(keys: list, value, field: str) -> dict:
    """Spread a list across its cells. A short list pads with _MISSING; a long one
    is truncated to the range. A non-list where an array was expected fills the
    whole range with _MISSING rather than writing a scalar into every cell."""
    if not isinstance(value, list):
        if value is not None:
            logger.warning("%s: expected a list for a %d-cell range, got %s; defaulting",
                           field, len(keys), type(value).__name__)
        return {k: _MISSING for k in keys}
    if len(value) != len(keys):
        logger.warning("%s: expected %d values, got %d; padding/truncating",
                       field, len(keys), len(value))
    return {k: (value[i] if i < len(value) else _MISSING) for i, k in enumerate(keys)}


def map_assumptions_to_template(assumptions: dict) -> dict:
    """Convert an Assumption Architect dict into the {"Sheet!Cell": value} dict the
    template-fill pipeline consumes.

    Every field in the schema gets a key in the result — one the AI omitted is
    defaulted rather than dropped, so the caller always receives the complete
    59-cell surface. Any extra key the AI returned (e.g. '_assumptions_notes') is
    carried through untouched; it has no cell mapping, and fill_template ignores
    keys without a '!', so it is inert downstream.
    """
    assumptions = assumptions or {}
    cell_map = load_cell_map()
    out = {}
    missing = []

    for field, spec in cell_map.items():
        keys = _expand(spec["cell"])
        present = field in assumptions
        if not present:
            missing.append(field)
        value = assumptions.get(field, _MISSING)

        if len(keys) == 1:
            out[keys[0]] = value
        else:
            out.update(_fill_range(keys, value, field))

    for key, value in assumptions.items():
        if key not in cell_map:
            out[key] = value

    if missing:
        logger.warning("%d assumption field(s) absent from AI output, defaulted: %s",
                       len(missing), missing)
    logger.info("mapped %d assumption fields -> %d template cells (%d defaulted)",
                len(cell_map), sum(len(_expand(s["cell"])) for s in cell_map.values()),
                len(missing))
    return out
