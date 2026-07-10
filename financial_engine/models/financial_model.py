"""
financial_model.py

The FinancialModel is the container for everything the engine CALCULATES from a
BusinessProfile. In Stage 1 it is intentionally a set of empty placeholders — no
calculations exist yet. Stage 2 will populate each section from its own
deterministic calculation module (Revenue Engine, Expense Engine, …).

This module also defines the shared value objects ValidationIssue /
ValidationReport. They live in the models layer (rather than the validators
package) because a ValidationReport is data — it is a section of the
FinancialModel and is produced by validators, so keeping it here lets validators
depend on models (the correct direction) without any circular import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .enums import Currency, Industry, ReportPurpose, ValidationSeverity


# ── Validation value objects ───────────────────────────────────────────────
@dataclass
class ValidationIssue:
    field: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    code: Optional[str] = None


@dataclass
class ValidationReport:
    """Result of running a validator. Aggregates issues and answers the one
    question callers care about: is this valid enough to proceed?"""
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, field: str, message: str,
            severity: ValidationSeverity = ValidationSeverity.ERROR,
            code: Optional[str] = None) -> None:
        self.issues.append(ValidationIssue(field=field, message=message,
                                           severity=severity, code=code))

    def merge(self, other: "ValidationReport") -> "ValidationReport":
        self.issues.extend(other.issues)
        return self

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def infos(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]

    @property
    def is_valid(self) -> bool:
        """Valid == no ERROR-severity issues (warnings/infos are allowed)."""
        return not self.errors

    def __bool__(self) -> bool:
        return self.is_valid


# ── Output section placeholders (populated in Stage 2+) ────────────────────
@dataclass
class _Section:
    """Base for every FinancialModel section. Stage 1 keeps them empty; each
    carries an `is_populated` flag and a free-form `data` bag so Stage-2 engines
    have somewhere to write without another schema change."""
    is_populated: bool = False
    data: Dict[str, object] = field(default_factory=dict)


@dataclass
class RevenueSection(_Section):
    """Revenue build-up. Populated by the Stage-2 Revenue Engine."""


@dataclass
class ExpenseSection(_Section):
    """Operating expenses. Populated by the Stage-2 Expense Engine."""


@dataclass
class PayrollSection(_Section):
    """Headcount & payroll cost. Populated by the Stage-2 Payroll Engine."""


@dataclass
class CapexSection(_Section):
    """Capital expenditure schedule."""


@dataclass
class WorkingCapitalSection(_Section):
    """Working-capital build-up and change."""


@dataclass
class LoanScheduleSection(_Section):
    """Debt drawdown, interest and repayment schedule."""


@dataclass
class DepreciationSection(_Section):
    """Asset block and depreciation schedule."""


@dataclass
class ProfitAndLossSection(_Section):
    """Projected profit & loss statement."""


@dataclass
class BalanceSheetSection(_Section):
    """Projected balance sheet."""


@dataclass
class CashFlowSection(_Section):
    """Projected cash-flow statement."""


@dataclass
class RatiosSection(_Section):
    """Financial ratios (margins, coverage, returns)."""


@dataclass
class ValuationSection(_Section):
    """DCF / valuation outputs (NPV, IRR, EV)."""


@dataclass
class DashboardKpiSection(_Section):
    """Headline KPIs for dashboards."""


@dataclass
class ChartsSection(_Section):
    """Chart specifications for downstream renderers."""


@dataclass
class ModelMeta:
    """Pass-through context copied from the profile — NOT a calculation."""
    industry: Optional[Industry] = None
    purpose: Optional[ReportPurpose] = None
    currency: Optional[Currency] = None
    projection_years: Optional[int] = None
    engine_version: str = "1.0"


# ── Aggregate root ─────────────────────────────────────────────────────────
@dataclass
class FinancialModel:
    """All calculated outputs for a business. Empty in Stage 1."""
    revenue: RevenueSection = field(default_factory=RevenueSection)
    expenses: ExpenseSection = field(default_factory=ExpenseSection)
    payroll: PayrollSection = field(default_factory=PayrollSection)
    capex: CapexSection = field(default_factory=CapexSection)
    working_capital: WorkingCapitalSection = field(default_factory=WorkingCapitalSection)
    loan_schedule: LoanScheduleSection = field(default_factory=LoanScheduleSection)
    depreciation: DepreciationSection = field(default_factory=DepreciationSection)
    profit_and_loss: ProfitAndLossSection = field(default_factory=ProfitAndLossSection)
    balance_sheet: BalanceSheetSection = field(default_factory=BalanceSheetSection)
    cash_flow: CashFlowSection = field(default_factory=CashFlowSection)
    ratios: RatiosSection = field(default_factory=RatiosSection)
    valuation: ValuationSection = field(default_factory=ValuationSection)
    dashboard_kpis: DashboardKpiSection = field(default_factory=DashboardKpiSection)
    charts: ChartsSection = field(default_factory=ChartsSection)
    validation_report: Optional[ValidationReport] = None
    meta: ModelMeta = field(default_factory=ModelMeta)

    @property
    def is_computed(self) -> bool:
        """True once any section has been populated by a Stage-2 engine."""
        return any(getattr(self, name).is_populated for name in (
            "revenue", "expenses", "payroll", "capex", "working_capital",
            "loan_schedule", "depreciation", "profit_and_loss", "balance_sheet",
            "cash_flow", "ratios", "valuation", "dashboard_kpis", "charts"))

    @classmethod
    def empty(cls) -> "FinancialModel":
        """An empty model with every section present but unpopulated."""
        return cls()
