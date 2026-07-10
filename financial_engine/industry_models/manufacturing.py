"""
manufacturing.py

Concrete industry model for Manufacturing. It DESCRIBES the manufacturing world —
the inputs it needs, the drivers that will power the model, its benchmark
assumptions, and its integrity rules. It performs NO financial calculations; the
numbers here are static industry benchmarks (configuration), not computed values.
"""

from __future__ import annotations

from typing import List

from ..models.assumptions import (
    Assumptions,
    CostAssumptions,
    CostOfCapital,
    DepreciationAssumptions,
    FinancingAssumptions,
    MacroAssumptions,
    RevenueAssumptions,
    WorkingCapitalAssumptions,
)
from ..models.business_profile import BusinessProfile
from ..models.enums import DepreciationMethod, Industry, ValidationSeverity
from ..models.financial_model import ValidationReport
from .base import BaseIndustryModel, DriverCategory, DriverDefinition, FieldType, InputField


class ManufacturingModel(BaseIndustryModel):
    """Manufacturing: goods produced from raw materials via plant & machinery."""

    industry = Industry.MANUFACTURING
    display_name = "Manufacturing"

    # ── required inputs ────────────────────────────────────────────────────
    def required_inputs(self) -> List[InputField]:
        return [
            InputField("installed_capacity", "Installed Capacity", FieldType.NUMBER,
                       unit="units/year", profile_path="production.installed_capacity",
                       description="Rated annual production capacity."),
            InputField("capacity_unit", "Capacity Unit", FieldType.TEXT, required=False,
                       profile_path="production.capacity_unit",
                       description="Unit of measure for capacity (e.g. tonnes, pieces)."),
            InputField("selling_price_per_unit", "Selling Price / Unit", FieldType.CURRENCY,
                       profile_path="sales.products[].unit_selling_price",
                       description="Average realisation per unit sold."),
            InputField("working_days_per_year", "Working Days / Year", FieldType.DAYS,
                       unit="days", profile_path="operations.working_days_per_year"),
            InputField("land_cost", "Land Cost", FieldType.CURRENCY, required=False,
                       profile_path="land.cost"),
            InputField("building_cost", "Building & Civil Cost", FieldType.CURRENCY,
                       profile_path="building.construction_cost"),
            InputField("machinery_cost", "Plant & Machinery Cost", FieldType.CURRENCY,
                       profile_path="machinery.total_cost"),
            InputField("raw_material_cost", "Annual Raw Material Cost", FieldType.CURRENCY,
                       required=False, profile_path=None,
                       description="Year-1 raw material cost at rated capacity."),
            InputField("labour_cost", "Annual Labour Cost", FieldType.CURRENCY, required=False,
                       profile_path=None),
            InputField("power_fuel_cost", "Annual Power & Fuel Cost", FieldType.CURRENCY,
                       required=False, profile_path=None),
            InputField("term_loan", "Term Loan", FieldType.CURRENCY, required=False,
                       profile_path="funding.term_loan"),
            InputField("own_contribution", "Promoter Contribution", FieldType.CURRENCY,
                       required=False, profile_path="funding.own_contribution"),
            InputField("interest_rate", "Interest Rate", FieldType.PERCENT, required=False,
                       unit="%", profile_path="funding.interest_rate_pct"),
            InputField("tax_rate", "Income Tax Rate", FieldType.PERCENT, required=False,
                       unit="%", profile_path="tax.income_tax_rate_pct"),
        ]

    # ── financial drivers ──────────────────────────────────────────────────
    def financial_drivers(self) -> List[DriverDefinition]:
        return [
            DriverDefinition("installed_capacity", "Installed Capacity", DriverCategory.CAPACITY,
                             unit="units/year", description="Rated annual output."),
            DriverDefinition("capacity_utilisation", "Capacity Utilisation", DriverCategory.OPERATIONS,
                             unit="%", benchmark=60.0,
                             description="Share of installed capacity actually used (ramps by year)."),
            DriverDefinition("working_days", "Working Days / Year", DriverCategory.OPERATIONS,
                             unit="days", benchmark=300.0),
            DriverDefinition("yield_pct", "Production Yield", DriverCategory.OPERATIONS,
                             unit="%", benchmark=98.0,
                             description="Share of production that is good output."),
            DriverDefinition("scrap_pct", "Production Loss / Scrap", DriverCategory.OPERATIONS,
                             unit="%", benchmark=2.0,
                             description="Share of yielded output lost as scrap."),
            DriverDefinition("selling_price", "Selling Price / Unit", DriverCategory.PRICING,
                             unit="currency/unit"),
            DriverDefinition("raw_material_pct", "Raw Material", DriverCategory.COST_STRUCTURE,
                             unit="% of sales", benchmark=55.0),
            DriverDefinition("labour_pct", "Direct Labour", DriverCategory.COST_STRUCTURE,
                             unit="% of sales", benchmark=10.0),
            DriverDefinition("power_fuel_pct", "Power & Fuel", DriverCategory.COST_STRUCTURE,
                             unit="% of sales", benchmark=6.0),
            DriverDefinition("other_overhead_pct", "Other Manufacturing Overhead",
                             DriverCategory.COST_STRUCTURE, unit="% of sales", benchmark=5.0),
            DriverDefinition("inventory_days", "Inventory Holding", DriverCategory.WORKING_CAPITAL,
                             unit="days", benchmark=60.0),
            DriverDefinition("receivable_days", "Receivable Period", DriverCategory.WORKING_CAPITAL,
                             unit="days", benchmark=45.0),
            DriverDefinition("payable_days", "Payable Period", DriverCategory.WORKING_CAPITAL,
                             unit="days", benchmark=45.0),
            DriverDefinition("interest_rate", "Interest Rate", DriverCategory.FINANCING,
                             unit="%", benchmark=12.0),
        ]

    # ── default benchmark assumptions ──────────────────────────────────────
    def default_assumptions(self) -> Assumptions:
        return Assumptions(
            macro=MacroAssumptions(projection_years=5, inflation_pct=6.0),
            cost_of_capital=CostOfCapital(wacc_pct=15.0, cost_of_equity_pct=18.0,
                                          cost_of_debt_pct=12.0, terminal_growth_pct=3.0),
            revenue=RevenueAssumptions(base_growth_pct=10.0,
                                       ramp_by_year={1: 0.60, 2: 0.70, 3: 0.80, 4: 0.85, 5: 0.90}),
            costs=CostAssumptions(gross_margin_pct=32.0, opex_ratio_pct=9.0,
                                  payroll_ratio_pct=11.0, salary_increment_pct=8.0),
            working_capital=WorkingCapitalAssumptions(receivable_days=45, inventory_days=60,
                                                      payable_days=45),
            depreciation=DepreciationAssumptions(method=DepreciationMethod.STRAIGHT_LINE,
                                                 useful_life_years=15, residual_value_pct=10.0),
            financing=FinancingAssumptions(interest_rate_pct=12.0, loan_tenure_years=7,
                                           moratorium_months=12),
            extra={
                "raw_material_pct": 55.0,
                "labour_pct": 10.0,
                "power_fuel_pct": 6.0,
                "other_overhead_pct": 5.0,
                "yield_pct": 98.0,
                "scrap_pct": 2.0,
            },
        )

    # ── industry-specific validation (no math) ─────────────────────────────
    def validate_profile(self, profile: BusinessProfile) -> ValidationReport:
        report = ValidationReport()

        capacity = profile.production.installed_capacity
        if capacity is None:
            report.add("production.installed_capacity",
                       "Installed capacity is required for a manufacturing model.",
                       severity=ValidationSeverity.WARNING, code="mfg_capacity_missing")
        elif capacity <= 0:
            report.add("production.installed_capacity",
                       "Installed capacity must be greater than 0.",
                       code="mfg_capacity_positive")

        if not (profile.machinery.items or profile.machinery.total_cost):
            report.add("machinery",
                       "Plant & machinery cost is expected for a manufacturing project.",
                       severity=ValidationSeverity.WARNING, code="mfg_machinery_missing")

        if profile.production.capacity_unit is None:
            report.add("production.capacity_unit",
                       "Capacity unit of measure is not set.",
                       severity=ValidationSeverity.INFO, code="mfg_capacity_unit_missing")

        return report
