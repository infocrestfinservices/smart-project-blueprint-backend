"""
financial_validator.py

Placeholder for OUTPUT validation. Once the Stage-2 engines populate a
FinancialModel, this validator will check the results for internal consistency
(e.g. balance sheet ties to zero, cash never impossibly negative, ratios in
sane ranges). Stage 1 has no calculations to check, so it returns an empty,
valid report.

The rule-list shape mirrors BusinessProfileValidator so adding checks later is
the same one-line append.
"""

from __future__ import annotations

from typing import Callable, List

from ..models.financial_model import FinancialModel, ValidationReport

Rule = Callable[[FinancialModel, ValidationReport], None]

# No output rules yet — populated in Stage 2+.
DEFAULT_RULES: List[Rule] = []


class FinancialModelValidator:
    def __init__(self, rules: List[Rule] | None = None) -> None:
        self.rules: List[Rule] = list(rules) if rules is not None else list(DEFAULT_RULES)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def validate(self, model: FinancialModel) -> ValidationReport:
        report = ValidationReport()
        for rule in self.rules:
            rule(model, report)
        return report
