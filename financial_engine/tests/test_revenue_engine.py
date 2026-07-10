"""
Unit tests for the Stage-2B Manufacturing Revenue Engine.

Run with the stdlib:
    python -m unittest financial_engine.tests.test_revenue_engine
(or `pytest` from the backend directory).

Focus: deterministic behaviour, monotonicity, validation, multi-product totals,
and correct storage into FinancialModel.revenue (and nothing else).
"""

import unittest

from financial_engine.calculations.revenue import (
    ManufacturingRevenueEngine,
    ProjectionTimeline,
    RevenueValidator,
    YearlySeries,
)
from financial_engine.industry_models import ManufacturingModel
from financial_engine.models import BusinessProfile, Currency, FinancialModel, Industry
from financial_engine.models.business_profile import ProductLine, SalesProduct

MODEL = ManufacturingModel()


def make_profile(capacity=100_000, price=100.0, util=1.0, products=None):
    """A minimal, valid manufacturing profile with a flat utilisation ramp."""
    p = BusinessProfile.empty()
    p.industry.industry = Industry.MANUFACTURING
    p.currency = Currency.INR
    p.production.installed_capacity = capacity
    p.production.capacity_unit = "units"
    p.sales.products = products if products is not None else [
        SalesProduct(name="Main", unit_selling_price=price)]
    p.operations.capacity_utilisation_by_year = {y: util for y in range(1, 6)}
    return p


def y1_revenue(profile):
    return ManufacturingRevenueEngine().project(profile, MODEL).total_revenue.year(1)


class MonotonicityTests(unittest.TestCase):
    def test_increasing_capacity_increases_revenue(self):
        self.assertGreater(y1_revenue(make_profile(capacity=200_000)),
                           y1_revenue(make_profile(capacity=100_000)))

    def test_increasing_selling_price_increases_revenue(self):
        self.assertGreater(y1_revenue(make_profile(price=150.0)),
                           y1_revenue(make_profile(price=100.0)))

    def test_increasing_utilisation_increases_revenue(self):
        self.assertGreater(y1_revenue(make_profile(util=0.9)),
                           y1_revenue(make_profile(util=0.5)))


class ValidationTests(unittest.TestCase):
    def test_zero_capacity_triggers_validation(self):
        proj = ManufacturingRevenueEngine().project(make_profile(capacity=0), MODEL)
        self.assertFalse(proj.is_valid)
        self.assertIn("revenue_capacity_positive", {i.code for i in proj.validation.issues})
        self.assertEqual(proj.total_revenue.year(1), 0.0)

    def test_negative_price_triggers_validation(self):
        proj = ManufacturingRevenueEngine().project(make_profile(price=-10.0), MODEL)
        self.assertFalse(proj.is_valid)
        self.assertIn("revenue_price_positive", {i.code for i in proj.validation.issues})

    def test_utilisation_out_of_range_flagged_by_validator(self):
        report = RevenueValidator().validate_inputs(
            product_name="X", installed_capacity=100, selling_price=10,
            utilisation=YearlySeries([1.5]), yield_pct=0.98, scrap_pct=0.02)
        self.assertIn("revenue_utilisation_range", {i.code for i in report.issues})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.proj = ManufacturingRevenueEngine().project(make_profile(capacity=100_000, price=100.0), MODEL)
        self.line = self.proj.products[0]

    def test_saleable_never_exceeds_production(self):
        for i in range(1, self.proj.years + 1):
            self.assertLessEqual(self.line.saleable_quantity.year(i),
                                 self.line.actual_production.year(i) + 1e-6)

    def test_yield_and_scrap_reduce_saleable(self):
        # yield 98% + scrap 2% => saleable strictly below raw production.
        self.assertLess(self.line.saleable_quantity.year(1),
                        self.line.actual_production.year(1))

    def test_revenue_equals_saleable_times_price(self):
        for i in range(1, self.proj.years + 1):
            expected = self.line.saleable_quantity.year(i) * self.line.selling_price.year(i)
            self.assertAlmostEqual(self.line.revenue.year(i), expected, places=4)


class MultiProductTests(unittest.TestCase):
    def _multi_profile(self):
        p = make_profile()
        p.production.product_lines = [
            ProductLine(name="A", installed_capacity=100_000, capacity_unit="units"),
            ProductLine(name="B", installed_capacity=50_000, capacity_unit="units"),
        ]
        p.sales.products = [
            SalesProduct(name="A", unit_selling_price=100.0),
            SalesProduct(name="B", unit_selling_price=200.0),
        ]
        return p

    def test_multi_product_totals(self):
        proj = ManufacturingRevenueEngine().project(self._multi_profile(), MODEL)
        self.assertEqual(len(proj.products), 2)
        for i in range(1, proj.years + 1):
            summed = sum(pl.revenue.year(i) for pl in proj.products)
            self.assertAlmostEqual(proj.total_revenue.year(i), summed, places=4)

    def test_second_product_contributes_revenue(self):
        proj = ManufacturingRevenueEngine().project(self._multi_profile(), MODEL)
        self.assertGreater(proj.product("B").revenue.year(1), 0)


class IntegrationTests(unittest.TestCase):
    def test_projection_stored_in_financial_model_only(self):
        fm = FinancialModel.empty()
        engine = ManufacturingRevenueEngine()
        proj = engine.run(make_profile(), MODEL, fm)

        # Revenue section populated with the projection.
        self.assertTrue(fm.revenue.is_populated)
        self.assertIs(fm.revenue.data["projection"], proj)
        self.assertTrue(fm.is_computed)

        # Every OTHER section remains untouched.
        for name in ("expenses", "payroll", "capex", "working_capital", "loan_schedule",
                     "depreciation", "profit_and_loss", "balance_sheet", "cash_flow",
                     "ratios", "valuation", "dashboard_kpis", "charts"):
            self.assertFalse(getattr(fm, name).is_populated, msg=f"{name} was modified")

    def test_deterministic_output(self):
        profile = make_profile()
        a = ManufacturingRevenueEngine().project(profile, MODEL).total_revenue.as_list()
        b = ManufacturingRevenueEngine().project(profile, MODEL).total_revenue.as_list()
        self.assertEqual(a, b)


class TimelineTests(unittest.TestCase):
    def test_timeline_has_five_years_by_default(self):
        proj = ManufacturingRevenueEngine().project(make_profile(), MODEL)
        self.assertEqual(proj.years, 5)
        self.assertEqual(proj.timeline.indices(), [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
