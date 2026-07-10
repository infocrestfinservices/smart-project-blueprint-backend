"""
business_profile.py

The BusinessProfile is the single structured representation of a business as a
set of FACTS — everything a user or the AI layer supplies about the project. It
holds NO calculated values (no revenue, profit, IRR, cash flow); those belong to
the FinancialModel. Keeping facts and outputs strictly separate is what makes the
engine deterministic and testable: the same BusinessProfile always yields the
same FinancialModel.

Implemented with standard-library dataclasses so the model is dependency-free and
can hold partial / not-yet-valid data (validation is a separate concern — see the
validators package). Every field is optional and defaults to empty, so a bare
`BusinessProfile()` is a valid, fully-structured skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .enums import (
    AreaUnit,
    BusinessConstitution,
    Currency,
    DataSource,
    FundingSourceType,
    Industry,
    ReportPurpose,
)


# ── Section models ─────────────────────────────────────────────────────────
@dataclass
class GeneralInformation:
    business_name: Optional[str] = None
    promoter_name: Optional[str] = None
    promoter_experience_years: Optional[float] = None
    promoter_background: Optional[str] = None
    constitution: Optional[BusinessConstitution] = None
    business_description: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class ProjectInformation:
    title: Optional[str] = None
    summary: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    target_market: Optional[str] = None
    target_customers: Optional[str] = None
    competitive_advantage: Optional[str] = None


@dataclass
class IndustryInfo:
    industry: Optional[Industry] = None
    sub_industry: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class PurposeInfo:
    purpose: Optional[ReportPurpose] = None
    financial_format: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class CountryInfo:
    country_name: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None


@dataclass
class FundingSource:
    source_type: Optional[FundingSourceType] = None
    amount: Optional[float] = None
    description: Optional[str] = None


@dataclass
class Funding:
    own_contribution: Optional[float] = None
    term_loan: Optional[float] = None
    working_capital_loan: Optional[float] = None
    other_sources: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    loan_tenure_years: Optional[float] = None
    moratorium_months: Optional[float] = None
    sources: List[FundingSource] = field(default_factory=list)


@dataclass
class ProjectCost:
    total_project_cost: Optional[float] = None
    preoperative_expenses: Optional[float] = None
    contingency: Optional[float] = None
    margin_money_for_wc: Optional[float] = None


@dataclass
class Land:
    area_value: Optional[float] = None
    area_unit: Optional[AreaUnit] = None
    cost: Optional[float] = None
    is_owned: Optional[bool] = None
    lease_annual_rent: Optional[float] = None
    lease_years: Optional[float] = None


@dataclass
class Building:
    built_up_area: Optional[float] = None
    area_unit: Optional[AreaUnit] = None
    construction_cost: Optional[float] = None
    construction_period_months: Optional[float] = None


@dataclass
class MachineryItem:
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit_cost: Optional[float] = None
    is_imported: Optional[bool] = None


@dataclass
class Machinery:
    items: List[MachineryItem] = field(default_factory=list)
    total_cost: Optional[float] = None
    installation_cost: Optional[float] = None


@dataclass
class WorkingCapital:
    requirement: Optional[float] = None
    margin_pct: Optional[float] = None
    inventory_days: Optional[float] = None
    receivable_days: Optional[float] = None
    payable_days: Optional[float] = None


@dataclass
class Operations:
    working_days_per_year: Optional[float] = None
    shifts_per_day: Optional[float] = None
    hours_per_shift: Optional[float] = None
    # Planned capacity utilisation by projection year, e.g. {1: 0.6, 2: 0.75}.
    capacity_utilisation_by_year: Dict[int, float] = field(default_factory=dict)


@dataclass
class ProductLine:
    name: Optional[str] = None
    installed_capacity: Optional[float] = None
    capacity_unit: Optional[str] = None


@dataclass
class Production:
    installed_capacity: Optional[float] = None
    capacity_unit: Optional[str] = None
    product_lines: List[ProductLine] = field(default_factory=list)


@dataclass
class SalesProduct:
    name: Optional[str] = None
    unit_selling_price: Optional[float] = None
    year1_volume: Optional[float] = None
    annual_growth_pct: Optional[float] = None


@dataclass
class Sales:
    products: List[SalesProduct] = field(default_factory=list)
    credit_period_days: Optional[float] = None
    export_share_pct: Optional[float] = None


@dataclass
class EmployeeRole:
    title: Optional[str] = None
    department: Optional[str] = None
    headcount: Optional[int] = None
    monthly_salary: Optional[float] = None


@dataclass
class Employees:
    roles: List[EmployeeRole] = field(default_factory=list)
    total_headcount: Optional[int] = None
    annual_increment_pct: Optional[float] = None


@dataclass
class TaxInformation:
    income_tax_rate_pct: Optional[float] = None
    gst_rate_pct: Optional[float] = None
    other_levies_pct: Optional[float] = None


@dataclass
class Timeline:
    start_year: Optional[int] = None
    projection_years: Optional[int] = None
    fiscal_year_start_month: Optional[int] = None
    construction_start_month: Optional[int] = None
    commercial_operation_date: Optional[str] = None


@dataclass
class Metadata:
    """Audit / provenance. `created_at` is a caller-supplied string (never
    auto-stamped) so the engine stays deterministic."""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    source: DataSource = DataSource.UNKNOWN
    schema_version: str = "1.0"
    notes: Optional[str] = None
    external_ids: Dict[str, str] = field(default_factory=dict)


# ── Aggregate root ─────────────────────────────────────────────────────────
@dataclass
class BusinessProfile:
    """Complete, structured set of business facts. Contains NO calculated
    fields — outputs live in FinancialModel."""
    general: GeneralInformation = field(default_factory=GeneralInformation)
    project: ProjectInformation = field(default_factory=ProjectInformation)
    industry: IndustryInfo = field(default_factory=IndustryInfo)
    purpose: PurposeInfo = field(default_factory=PurposeInfo)
    country: CountryInfo = field(default_factory=CountryInfo)
    currency: Optional[Currency] = None
    funding: Funding = field(default_factory=Funding)
    project_cost: ProjectCost = field(default_factory=ProjectCost)
    land: Land = field(default_factory=Land)
    building: Building = field(default_factory=Building)
    machinery: Machinery = field(default_factory=Machinery)
    working_capital: WorkingCapital = field(default_factory=WorkingCapital)
    operations: Operations = field(default_factory=Operations)
    production: Production = field(default_factory=Production)
    sales: Sales = field(default_factory=Sales)
    employees: Employees = field(default_factory=Employees)
    tax: TaxInformation = field(default_factory=TaxInformation)
    timeline: Timeline = field(default_factory=Timeline)
    metadata: Metadata = field(default_factory=Metadata)

    @classmethod
    def empty(cls) -> "BusinessProfile":
        """A fully-structured, all-defaults profile — handy for tests and for
        the AI/user layer to fill in progressively."""
        return cls()
