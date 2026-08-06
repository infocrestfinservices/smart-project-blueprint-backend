"""
test_template_cell_mapper_manual.py

Standalone test for template_cell_mapper.build_template_cell_mapping using a MOCK
template definition and mock worksheet payloads. Verifies the resolved {sheet: {cell:
value}} map is exactly what the field->cell definition implies, and that malformed
inputs raise ValueError.

Run from backend/:
    python excel_writer/test_template_cell_mapper_manual.py
"""

import importlib.util
import sys
from pathlib import Path

# template_cell_mapper.py lives inside a dir named 'excel_writer' that also contains
# excel_writer.py (which shadows the package). Load this module by explicit path.
_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_template_cell_mapper_under_test",
                                               _HERE / "template_cell_mapper.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_template_cell_mapping = _mod.build_template_cell_mapping

fails = []


def ok(cond, label):
    print(f"   {'OK ' if cond else 'FAIL'}  {label}")
    if not cond:
        fails.append(label)


# ── MOCK worksheet payloads (shape as produced by financial_model_mapper) ──────
WORKSHEET_MAPPING = {
    "Dashboard": {
        "Revenue": [18_000_000, 22_050_000, 24_806_250, 27_783_000, 30_995_409],
        "IRR": 0.685,
        "NPV": 5_318_361,
        "EBITDA": [3_360_000, 4_100_000, 4_600_000, 5_100_000, 5_600_000],  # not mapped -> ignored
    },
    "ProfitLoss": {
        "pat": [1_349_812, 2_348_415, 2_977_041, 3_652_284, 4_377_286],
    },
}

# ── MOCK template definition (which A1 cells each field occupies) ──────────────
TEMPLATE_DEFINITION = {
    "Dashboard": {
        "Revenue": ["B5", "C5", "D5", "E5", "F5"],   # 5-year series across columns
        "IRR": "B7",                                  # scalar
        "NPV": "B8",                                  # scalar
    },
    "ProfitLoss": {
        "pat": ["D25", "E25", "F25", "G25", "H25"],
    },
}

EXPECTED = {
    "Dashboard": {
        "B5": 18_000_000, "C5": 22_050_000, "D5": 24_806_250, "E5": 27_783_000, "F5": 30_995_409,
        "B7": 0.685, "B8": 5_318_361,
    },
    "ProfitLoss": {
        "D25": 1_349_812, "E25": 2_348_415, "F25": 2_977_041, "G25": 3_652_284, "H25": 4_377_286,
    },
}


def main():
    print("=" * 74)
    print("TEMPLATE CELL MAPPER  (mock template definition)")
    print("=" * 74)

    result = build_template_cell_mapping(WORKSHEET_MAPPING, TEMPLATE_DEFINITION)

    print("\n1. Resolved cell map matches the hand-derived expectation:")
    ok(result == EXPECTED, "full {sheet: {cell: value}} equals EXPECTED")
    for sheet in EXPECTED:
        ok(result.get(sheet) == EXPECTED[sheet], f"{sheet} cells correct")

    print("\n   resolved map:")
    for sheet, cells in result.items():
        print(f"     {sheet}: {cells}")

    print("\n2. Only template-mapped fields appear (EBITDA has no cell -> excluded):")
    ok(all("EBITDA" not in v for v in [result["Dashboard"]]), "EBITDA not written")
    ok(set(result["Dashboard"].keys()) == {"B5", "C5", "D5", "E5", "F5", "B7", "B8"},
       "Dashboard cells are exactly the mapped ones")

    print("\n3. Malformed inputs raise ValueError:")
    cases = [
        ("worksheet_mapping not a dict",
         lambda: build_template_cell_mapping([], TEMPLATE_DEFINITION)),
        ("template_definition not a dict",
         lambda: build_template_cell_mapping(WORKSHEET_MAPPING, [])),
        ("worksheet in template has no payload",
         lambda: build_template_cell_mapping({"ProfitLoss": {"pat": [1] * 5}},
                                             {"Ghost": {"x": "A1"}})),
        ("required field missing from payload",
         lambda: build_template_cell_mapping({"Dashboard": {}},
                                             {"Dashboard": {"Revenue": ["A1"]}})),
        ("series length mismatch (5 cells, 3 values)",
         lambda: build_template_cell_mapping({"Dashboard": {"Revenue": [1, 2, 3]}},
                                             {"Dashboard": {"Revenue": ["A1", "B1", "C1", "D1", "E1"]}})),
        ("scalar cell but list value",
         lambda: build_template_cell_mapping({"Dashboard": {"Revenue": [1, 2, 3]}},
                                             {"Dashboard": {"Revenue": "A1"}})),
        ("series cell but scalar value",
         lambda: build_template_cell_mapping({"Dashboard": {"IRR": 0.1}},
                                             {"Dashboard": {"IRR": ["A1", "B1"]}})),
    ]
    for label, fn in cases:
        try:
            fn()
            ok(False, f"{label} -> should have raised")
        except ValueError as e:
            ok(True, f"{label} -> ValueError: {str(e).split(':',1)[1].strip()[:34]}")

    print("\n" + "=" * 74)
    if fails:
        print(f"FAILED — {len(fails)} check(s): {fails}")
        raise AssertionError("template_cell_mapper did not behave as specified")
    print("PASSED — payloads resolved into a workbook-ready {sheet: {cell: value}} map;")
    print("series/scalars placed correctly; unmapped fields skipped; malformed rejected.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
