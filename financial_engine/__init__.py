"""
financial_engine
=================

The deterministic financial calculation engine for the next-generation platform.
It is the intended single source of truth for all financial calculations that
future reports (Excel, Word, PDF, Dashboard) will consume.

Design principles
-----------------
* Independent of Excel, AI, and Word/PDF generation.
* Deterministic — the same BusinessProfile always yields the same FinancialModel.
* Modular, testable, and built for long-term growth.

STATUS — Stage 1 (Architecture only)
------------------------------------
This stage builds the foundation ONLY. There are NO financial calculations yet:

    * BusinessProfile  — structured business FACTS (no calculated fields)
    * FinancialModel   — empty placeholders for all calculated OUTPUTS
    * Assumptions      — empty container for future modelling drivers
    * validators       — profile integrity checks (+ output/assumption placeholders)
    * registry         — registration-based industry & purpose catalogues
    * FinancialEngine  — validate → load industry → return an EMPTY FinancialModel

It is completely separate from, and does not touch, the existing Excel pipeline
(services/excel_model_builder.py, including derive_assumptions()). Stage 2 will
add the Revenue / Expense / Payroll / … calculation modules on top of this.

Minimal usage
-------------
    from financial_engine import FinancialEngine, BusinessProfile

    engine = FinancialEngine()
    model = engine.build(BusinessProfile.empty())   # empty, validated model
"""

from .core import FinancialEngine, ProfileValidationError
from .industry_models import (
    BaseIndustryModel,
    DriverCategory,
    DriverDefinition,
    FieldType,
    InputField,
    ManufacturingModel,
)
from .models import (
    Assumptions,
    BusinessProfile,
    Currency,
    FinancialModel,
    Industry,
    ReportPurpose,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)
from .registry import industry_registry, purpose_registry
from .validators import (
    AssumptionValidator,
    BusinessProfileValidator,
    FinancialModelValidator,
)

__version__ = "1.1.0-stage2a"

__all__ = [
    "FinancialEngine",
    "ProfileValidationError",
    "BusinessProfile",
    "FinancialModel",
    "Assumptions",
    "Industry",
    "ReportPurpose",
    "Currency",
    "ValidationReport",
    "ValidationIssue",
    "ValidationSeverity",
    "BusinessProfileValidator",
    "FinancialModelValidator",
    "AssumptionValidator",
    "BaseIndustryModel",
    "ManufacturingModel",
    "InputField",
    "DriverDefinition",
    "FieldType",
    "DriverCategory",
    "industry_registry",
    "purpose_registry",
    "__version__",
]
