"""
business_validator.py

Validates a BusinessProfile against a set of rules and returns a ValidationReport.
Rules are plain callables `(profile, report) -> None` held in a list, so the rule
set is fully extensible — add a function, append it, done. No calculations here;
these are integrity checks on the input facts only.

A rule skips silently when the data it needs is absent (a partial, still-being-
filled profile is not an error); it only reports when a present value is invalid.
"""

from __future__ import annotations

from typing import Callable, List

from ..models.business_profile import BusinessProfile
from ..models.enums import ValidationSeverity
from ..models.financial_model import ValidationReport

Rule = Callable[[BusinessProfile, ValidationReport], None]


# ── Individual rules ───────────────────────────────────────────────────────
def project_cost_positive(profile: BusinessProfile, report: ValidationReport) -> None:
    cost = profile.project_cost.total_project_cost
    if cost is not None and cost <= 0:
        report.add("project_cost.total_project_cost",
                   "Project cost must be greater than 0.",
                   code="project_cost_positive")


def loan_within_project_cost(profile: BusinessProfile, report: ValidationReport) -> None:
    cost = profile.project_cost.total_project_cost
    debt = _sum(profile.funding.term_loan, profile.funding.working_capital_loan)
    if cost is not None and debt is not None and debt > cost:
        report.add("funding.loan",
                   "Total loan cannot exceed the project cost.",
                   code="loan_within_project_cost")


def employees_non_negative(profile: BusinessProfile, report: ValidationReport) -> None:
    total = profile.employees.total_headcount
    if total is not None and total < 0:
        report.add("employees.total_headcount",
                   "Employee count cannot be negative.",
                   code="employees_non_negative")
    for i, role in enumerate(profile.employees.roles):
        if role.headcount is not None and role.headcount < 0:
            report.add(f"employees.roles[{i}].headcount",
                       f"Headcount for '{role.title or 'role'}' cannot be negative.",
                       code="employees_non_negative")


def working_days_within_year(profile: BusinessProfile, report: ValidationReport) -> None:
    days = profile.operations.working_days_per_year
    if days is not None and not (0 <= days <= 365):
        report.add("operations.working_days_per_year",
                   "Working days per year must be between 0 and 365.",
                   code="working_days_within_year")


def selling_price_positive(profile: BusinessProfile, report: ValidationReport) -> None:
    products = profile.sales.products
    if not products:
        report.add("sales.products",
                   "No products / selling price defined.",
                   severity=ValidationSeverity.WARNING,
                   code="selling_price_missing")
        return
    for i, product in enumerate(products):
        price = product.unit_selling_price
        if price is not None and price <= 0:
            report.add(f"sales.products[{i}].unit_selling_price",
                       f"Selling price for '{product.name or 'product'}' must be greater than 0.",
                       code="selling_price_positive")


def interest_rate_reasonable(profile: BusinessProfile, report: ValidationReport) -> None:
    rate = profile.funding.interest_rate_pct
    if rate is not None and rate < 0:
        report.add("funding.interest_rate_pct",
                   "Interest rate cannot be negative.",
                   code="interest_rate_non_negative")


DEFAULT_RULES: List[Rule] = [
    project_cost_positive,
    loan_within_project_cost,
    employees_non_negative,
    working_days_within_year,
    selling_price_positive,
    interest_rate_reasonable,
]


# ── Validator ──────────────────────────────────────────────────────────────
class BusinessProfileValidator:
    """Runs a list of rules over a BusinessProfile. Pass a custom `rules` list to
    extend or override the defaults."""

    def __init__(self, rules: List[Rule] | None = None) -> None:
        self.rules: List[Rule] = list(rules) if rules is not None else list(DEFAULT_RULES)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def validate(self, profile: BusinessProfile) -> ValidationReport:
        report = ValidationReport()
        for rule in self.rules:
            rule(profile, report)
        return report


def _sum(*values):
    present = [v for v in values if v is not None]
    return sum(present) if present else None
