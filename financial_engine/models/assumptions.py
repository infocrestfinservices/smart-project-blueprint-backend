"""
assumptions.py

The Assumptions model is the structured set of DRIVERS the Stage-2 calculation
engines will consume (growth rates, margins, cost-of-capital, working-capital
days, depreciation policy, …). In Stage 1 it is a placeholder container only —
no derivation logic, no defaults populated.

IMPORTANT: this is NOT the legacy `derive_assumptions()` used by the existing
Excel pipeline (services/excel_model_builder.py). That function is untouched.
This is the V2 assumptions container that a future, dedicated assumptions module
will populate deterministically from a BusinessProfile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from .enums import Currency, DepreciationMethod


@dataclass
class MacroAssumptions:
    base_year: Optional[int] = None
    projection_years: Optional[int] = None
    inflation_pct: Optional[float] = None
    currency: Optional[Currency] = None


@dataclass
class CostOfCapital:
    wacc_pct: Optional[float] = None
    cost_of_equity_pct: Optional[float] = None
    cost_of_debt_pct: Optional[float] = None
    terminal_growth_pct: Optional[float] = None


@dataclass
class RevenueAssumptions:
    base_growth_pct: Optional[float] = None
    # Planned ramp / utilisation by projection year, e.g. {1: 0.6, 2: 0.8}.
    ramp_by_year: Dict[int, float] = field(default_factory=dict)


@dataclass
class CostAssumptions:
    gross_margin_pct: Optional[float] = None
    opex_ratio_pct: Optional[float] = None
    payroll_ratio_pct: Optional[float] = None
    salary_increment_pct: Optional[float] = None


@dataclass
class WorkingCapitalAssumptions:
    receivable_days: Optional[float] = None
    inventory_days: Optional[float] = None
    payable_days: Optional[float] = None


@dataclass
class DepreciationAssumptions:
    method: Optional[DepreciationMethod] = None
    useful_life_years: Optional[float] = None
    residual_value_pct: Optional[float] = None


@dataclass
class FinancingAssumptions:
    interest_rate_pct: Optional[float] = None
    loan_tenure_years: Optional[float] = None
    moratorium_months: Optional[float] = None


@dataclass
class Assumptions:
    """All modelling drivers, grouped. Empty in Stage 1."""
    macro: MacroAssumptions = field(default_factory=MacroAssumptions)
    cost_of_capital: CostOfCapital = field(default_factory=CostOfCapital)
    revenue: RevenueAssumptions = field(default_factory=RevenueAssumptions)
    costs: CostAssumptions = field(default_factory=CostAssumptions)
    working_capital: WorkingCapitalAssumptions = field(default_factory=WorkingCapitalAssumptions)
    depreciation: DepreciationAssumptions = field(default_factory=DepreciationAssumptions)
    financing: FinancingAssumptions = field(default_factory=FinancingAssumptions)
    # Free-form bag for industry-specific drivers a registry entry may add later.
    extra: Dict[str, object] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "Assumptions":
        return cls()
