"""
template_cell_mapper.py

Turns the workbook-INDEPENDENT worksheet payloads (from
financial_model_mapper.build_excel_mapping) into a workbook-SPECIFIC cell map, using a
template definition that says which A1 cell(s) each field occupies in a particular
workbook.

    worksheet_mapping  {sheet: {field: value}}         (what goes on each sheet)
            +
    template_definition {sheet: {field: "A1" | ["A1", "B1", ...]}}   (where it goes)
            ->
    {sheet: {cell: value}}                             (workbook-ready)

Pure resolver. It does NOT use openpyxl, does NOT load or write a workbook, does NOT
calculate, format, or touch formulas. It only looks each field up in the payload and
pairs its value(s) with the cell address(es) the template assigns.

Validation:
  * worksheet referenced by the template definition must have a payload,
  * every field the template maps must be present in that payload,
  * a series field's value length must match the number of cells the template gives it,
  * a scalar cell must not be handed a list value (and vice-versa).
Raises ValueError on any of these.

The result plugs straight into a writer that consumes {sheet: {cell: value}}.
"""

from __future__ import annotations


def build_template_cell_mapping(worksheet_mapping: dict, template_definition: dict) -> dict:
    """Resolve worksheet payloads against a template definition into {sheet: {cell:
    value}}. Only the fields named in template_definition are mapped (a payload field
    with no template cell is simply not written). Raises ValueError on malformed input.
    """
    fn = "build_template_cell_mapping"

    if not isinstance(worksheet_mapping, dict):
        raise ValueError(f"{fn}: worksheet_mapping must be a dict, "
                         f"got {type(worksheet_mapping).__name__}")
    if not isinstance(template_definition, dict):
        raise ValueError(f"{fn}: template_definition must be a dict, "
                         f"got {type(template_definition).__name__}")

    result: dict = {}
    for sheet, field_cells in template_definition.items():
        if not isinstance(field_cells, dict):
            raise ValueError(f"{fn}: template_definition[{sheet!r}] must be a dict, "
                             f"got {type(field_cells).__name__}")
        # worksheet must exist (have a payload) so its values can be resolved
        if sheet not in worksheet_mapping:
            raise ValueError(f"{fn}: worksheet {sheet!r} is in the template definition but "
                             f"has no payload in worksheet_mapping.")
        payload = worksheet_mapping[sheet]
        if not isinstance(payload, dict):
            raise ValueError(f"{fn}: worksheet_mapping[{sheet!r}] must be a dict, "
                             f"got {type(payload).__name__}")

        cell_values: dict = {}
        for field, target in field_cells.items():
            # every required (template-mapped) field must be present in the payload
            if field not in payload:
                raise ValueError(f"{fn}: required field {field!r} is not present in "
                                 f"worksheet_mapping[{sheet!r}].")
            value = payload[field]

            if isinstance(target, str):                       # scalar -> one cell
                if isinstance(value, (list, tuple)):
                    raise ValueError(f"{fn}: {sheet!r}.{field} maps to a single cell "
                                     f"{target!r} but its value is a list of {len(value)}.")
                cell_values[target] = value

            elif isinstance(target, (list, tuple)):           # series -> one cell per item
                if not isinstance(value, (list, tuple)):
                    raise ValueError(f"{fn}: {sheet!r}.{field} maps to {len(target)} cells "
                                     f"but its value is not a list.")
                if len(target) != len(value):
                    raise ValueError(f"{fn}: {sheet!r}.{field} series length mismatch — "
                                     f"template has {len(target)} cells, value has {len(value)}.")
                for cell, item in zip(target, value):
                    if not isinstance(cell, str):
                        raise ValueError(f"{fn}: {sheet!r}.{field} cell list must contain A1 "
                                         f"strings, got {type(cell).__name__}")
                    cell_values[cell] = item

            else:
                raise ValueError(f"{fn}: template_definition[{sheet!r}][{field!r}] must be an "
                                 f"A1 string or a list of A1 strings, got {type(target).__name__}")

        result[sheet] = cell_values

    return result
