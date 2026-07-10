"""
revenue_validator.py

Structured validation for the Revenue Engine — never silent failures. Split into
two phases so both the inputs and the computed result are checked:

    validate_inputs()      — per-product input sanity (capacity, price,
                             utilisation, yield, scrap) BEFORE calculation
    validate_projection()  — post-calculation consistency (production ≥ saleable,
                             revenue ≥ 0)

Both return a ValidationReport of structured issues.
"""

from __future__ import annotations

from typing import Optional

from ...models.enums import ValidationSeverity
from ...models.financial_model import ValidationReport
from .projection_period import YearlySeries

# Yield must lie in this (fractional) band to be meaningful.
_YIELD_MIN = 0.0
_YIELD_MAX = 1.0


class RevenueValidator:
    def validate_inputs(
        self,
        *,
        product_name: str,
        installed_capacity: Optional[float],
        selling_price: Optional[float],
        utilisation: YearlySeries,
        yield_pct: float,
        scrap_pct: float,
        report: Optional[ValidationReport] = None,
    ) -> ValidationReport:
        report = report if report is not None else ValidationReport()
        p = product_name or "product"

        if installed_capacity is None or installed_capacity <= 0:
            report.add(f"{p}.installed_capacity",
                       f"Installed capacity for '{p}' must be greater than 0.",
                       code="revenue_capacity_positive")

        if selling_price is None or selling_price <= 0:
            report.add(f"{p}.selling_price",
                       f"Selling price for '{p}' must be greater than 0.",
                       code="revenue_price_positive")

        for i, u in enumerate(utilisation.points, start=1):
            if not (0.0 <= u <= 1.0):
                report.add(f"{p}.capacity_utilisation[Y{i}]",
                           f"Capacity utilisation for '{p}' in Year {i} must be between 0% and 100%.",
                           code="revenue_utilisation_range")

        if not (_YIELD_MIN < yield_pct <= _YIELD_MAX):
            report.add(f"{p}.yield_pct",
                       f"Yield for '{p}' must be greater than 0% and at most 100%.",
                       code="revenue_yield_range")

        if not (0.0 <= scrap_pct < 1.0):
            report.add(f"{p}.scrap_pct",
                       f"Scrap/production loss for '{p}' must be between 0% and 100%.",
                       code="revenue_scrap_range")

        return report

    def validate_projection(self, projection, report: Optional[ValidationReport] = None) -> ValidationReport:
        report = report if report is not None else ValidationReport()
        for line in projection.products:
            for i in range(1, projection.years + 1):
                production = line.actual_production.year(i)
                saleable = line.saleable_quantity.year(i)
                revenue = line.revenue.year(i)
                if saleable > production + 1e-6:
                    report.add(f"{line.name}.saleable_quantity[Y{i}]",
                               f"Saleable quantity cannot exceed production in Year {i}.",
                               code="revenue_saleable_le_production")
                if revenue < -1e-6:
                    report.add(f"{line.name}.revenue[Y{i}]",
                               f"Revenue cannot be negative in Year {i}.",
                               code="revenue_non_negative")
        return report
