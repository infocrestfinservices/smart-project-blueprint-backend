"""
Unit tests for the Stage-2A Industry Modeling Framework.

Runnable with the stdlib (no pytest required):
    python -m unittest financial_engine.tests.test_industry_models
(or simply `pytest` from the backend directory).

These tests assert ARCHITECTURE only — no financial calculations exist yet.
"""

import unittest

from financial_engine import FinancialEngine, industry_registry
from financial_engine.industry_models import (
    BaseIndustryModel,
    DriverCategory,
    DriverDefinition,
    FieldType,
    InputField,
    ManufacturingModel,
)
from financial_engine.models import (
    Assumptions,
    BusinessProfile,
    Industry,
    ReportPurpose,
)
from financial_engine.models.assumptions import Assumptions as AssumptionsType


class RegistryReturnsModelTests(unittest.TestCase):
    def test_registry_returns_manufacturing_model_instance(self):
        model = industry_registry.get(Industry.MANUFACTURING)
        self.assertIsInstance(model, ManufacturingModel)
        self.assertIsInstance(model, BaseIndustryModel)
        self.assertEqual(model.industry, Industry.MANUFACTURING)
        self.assertEqual(model.display_name, "Manufacturing")

    def test_unbuilt_industry_resolves_to_none(self):
        # Software model isn't implemented yet in Stage 2A.
        self.assertIsNone(industry_registry.get_or_none(Industry.SOFTWARE))
        self.assertFalse(industry_registry.is_registered(Industry.SOFTWARE))

    def test_engine_resolves_model_through_registry(self):
        profile = BusinessProfile.empty()
        profile.industry.industry = Industry.MANUFACTURING
        resolved = FinancialEngine().resolve_industry_model(profile)
        self.assertIsInstance(resolved, ManufacturingModel)


class RequiredInputsTests(unittest.TestCase):
    def setUp(self):
        self.model = ManufacturingModel()
        self.inputs = self.model.required_inputs()

    def test_returns_input_field_objects(self):
        self.assertTrue(self.inputs)
        self.assertTrue(all(isinstance(f, InputField) for f in self.inputs))
        self.assertTrue(all(isinstance(f.field_type, FieldType) for f in self.inputs))

    def test_contains_expected_manufacturing_fields(self):
        keys = set(self.model.input_keys())
        expected = {
            "installed_capacity", "selling_price_per_unit", "working_days_per_year",
            "building_cost", "machinery_cost", "raw_material_cost", "labour_cost",
        }
        self.assertTrue(expected.issubset(keys),
                        msg=f"missing: {expected - keys}")

    def test_keys_are_unique(self):
        keys = self.model.input_keys()
        self.assertEqual(len(keys), len(set(keys)))


class FinancialDriversTests(unittest.TestCase):
    def setUp(self):
        self.model = ManufacturingModel()
        self.drivers = self.model.financial_drivers()

    def test_returns_driver_definition_objects(self):
        self.assertTrue(self.drivers)
        self.assertTrue(all(isinstance(d, DriverDefinition) for d in self.drivers))
        self.assertTrue(all(isinstance(d.category, DriverCategory) for d in self.drivers))

    def test_contains_expected_drivers(self):
        keys = set(self.model.driver_keys())
        expected = {
            "capacity_utilisation", "working_days", "selling_price",
            "raw_material_pct", "labour_pct", "inventory_days",
            "receivable_days", "payable_days",
        }
        self.assertTrue(expected.issubset(keys), msg=f"missing: {expected - keys}")

    def test_cost_and_wc_drivers_carry_benchmarks(self):
        rm = self.model.get_driver("raw_material_pct")
        self.assertIsNotNone(rm)
        self.assertEqual(rm.category, DriverCategory.COST_STRUCTURE)
        self.assertIsNotNone(rm.benchmark)
        recv = self.model.get_driver("receivable_days")
        self.assertEqual(recv.category, DriverCategory.WORKING_CAPITAL)
        self.assertGreater(recv.benchmark, 0)


class DefaultAssumptionsTests(unittest.TestCase):
    def setUp(self):
        self.assumptions = ManufacturingModel().default_assumptions()

    def test_returns_assumptions_structure(self):
        self.assertIsInstance(self.assumptions, AssumptionsType)
        self.assertIsInstance(self.assumptions, Assumptions)
        # Every section object is present.
        for section in ("macro", "cost_of_capital", "revenue", "costs",
                        "working_capital", "depreciation", "financing"):
            self.assertIsNotNone(getattr(self.assumptions, section))

    def test_benchmarks_are_populated_and_sane(self):
        a = self.assumptions
        self.assertIsNotNone(a.costs.gross_margin_pct)
        self.assertTrue(0 < a.costs.gross_margin_pct <= 100)
        self.assertIsNotNone(a.cost_of_capital.wacc_pct)
        self.assertTrue(0 < a.cost_of_capital.wacc_pct <= 100)
        self.assertTrue(a.cost_of_capital.terminal_growth_pct < a.cost_of_capital.wacc_pct)
        self.assertGreater(a.working_capital.inventory_days, 0)
        self.assertEqual(a.macro.projection_years, 5)

    def test_industry_specific_extras_present(self):
        self.assertIn("raw_material_pct", self.assumptions.extra)
        self.assertIn("labour_pct", self.assumptions.extra)


class EngineNoCalculationTests(unittest.TestCase):
    def test_build_resolves_model_but_computes_nothing(self):
        profile = BusinessProfile.empty()
        profile.industry.industry = Industry.MANUFACTURING
        profile.purpose.purpose = ReportPurpose.FEASIBILITY_STUDY
        model = FinancialEngine().build(profile)
        self.assertEqual(model.meta.industry, Industry.MANUFACTURING)
        self.assertFalse(model.is_computed)              # no calculations happened
        self.assertIsNotNone(model.validation_report)

    def test_manufacturing_validation_flags_missing_capacity(self):
        report = ManufacturingModel().validate_profile(BusinessProfile.empty())
        codes = {i.code for i in report.issues}
        self.assertIn("mfg_capacity_missing", codes)


if __name__ == "__main__":
    unittest.main()
