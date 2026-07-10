"""
assumption_validator.py

Placeholder for validating the Stage-2 Assumptions container (e.g. rates within
0–100%, positive useful life, terminal growth < WACC). Stage 1 defines no
business rules yet; it returns an empty, valid report and provides the same
extensible rule-list shape as the other validators.
"""

from __future__ import annotations

from typing import Callable, List

from ..models.assumptions import Assumptions
from ..models.financial_model import ValidationReport

Rule = Callable[[Assumptions, ValidationReport], None]

# No assumption rules yet — populated in Stage 2+.
DEFAULT_RULES: List[Rule] = []


class AssumptionValidator:
    def __init__(self, rules: List[Rule] | None = None) -> None:
        self.rules: List[Rule] = list(rules) if rules is not None else list(DEFAULT_RULES)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def validate(self, assumptions: Assumptions) -> ValidationReport:
        report = ValidationReport()
        for rule in self.rules:
            rule(assumptions, report)
        return report
