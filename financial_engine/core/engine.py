"""
engine.py

The FinancialEngine is the single public entry point of the module. Its Stage-1
contract is deliberately small and free of any calculation:

    BusinessProfile
        ↓  validate the profile (integrity of the facts)
        ↓  load the industry definition from the registry
        ↓  return an EMPTY FinancialModel (with the validation report + context)

Stage 2 will slot the calculation engines (revenue, expense, payroll, …) between
"load industry" and "return model" without changing this interface.

Dependencies are injected (registries + validators) so the engine is trivially
testable and never reaches into global state implicitly.
"""

from __future__ import annotations

from typing import Optional

from ..industry_models.base import BaseIndustryModel
from ..models.business_profile import BusinessProfile
from ..models.enums import ValidationSeverity
from ..models.financial_model import FinancialModel, ModelMeta, ValidationReport
from ..registry import (
    IndustryRegistry,
    PurposeRegistry,
    industry_registry as default_industry_registry,
    purpose_registry as default_purpose_registry,
)
from ..validators import BusinessProfileValidator


class ProfileValidationError(Exception):
    """Raised by build(strict=True) when the profile has ERROR-severity issues."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        messages = "; ".join(f"{i.field}: {i.message}" for i in report.errors)
        super().__init__(f"BusinessProfile failed validation — {messages}")


class FinancialEngine:
    """Deterministic engine skeleton. Same profile in → same model out."""

    def __init__(
        self,
        industry_registry: Optional[IndustryRegistry] = None,
        purpose_registry: Optional[PurposeRegistry] = None,
        business_validator: Optional[BusinessProfileValidator] = None,
    ) -> None:
        self.industry_registry = industry_registry or default_industry_registry
        self.purpose_registry = purpose_registry or default_purpose_registry
        self.business_validator = business_validator or BusinessProfileValidator()

    # -- public API ---------------------------------------------------------
    def validate(self, profile: BusinessProfile) -> ValidationReport:
        """Run the profile through the business validator and return the report."""
        return self.business_validator.validate(profile)

    def resolve_industry_model(self, profile: BusinessProfile) -> Optional[BaseIndustryModel]:
        """Look up the industry model for a profile (or None if unset/unbuilt)."""
        return self.industry_registry.get_or_none(profile.industry.industry)

    def build(self, profile: BusinessProfile, *, strict: bool = False) -> FinancialModel:
        """Validate → resolve industry model → return an empty FinancialModel.

        Stage 2A still performs NO financial calculations. The engine resolves the
        correct industry model through the registry and runs its industry-specific
        validation, but does not execute any calculation. Every output section of
        the returned model is present but unpopulated.

        strict=True raises ProfileValidationError if the profile has any
        ERROR-severity issues; the default is lenient so partial profiles still
        return a (flagged) model.
        """
        # 1. Validate the input facts (generic business rules).
        report = self.business_validator.validate(profile)

        # 2. Resolve the industry model (registry lookup, never if/else).
        industry = profile.industry.industry
        industry_model = self.industry_registry.get_or_none(industry)
        if industry is None:
            report.add("industry.industry", "No industry selected.",
                       severity=ValidationSeverity.WARNING, code="industry_missing")
        elif industry_model is None:
            report.add("industry.industry",
                       f"No industry model is available yet for '{industry.value}'.",
                       severity=ValidationSeverity.WARNING, code="industry_model_missing")
        else:
            # 3. Industry-specific validation (still no calculations).
            report.merge(industry_model.validate_profile(profile))

        # 4. Gate on hard errors when strict.
        if strict and not report.is_valid:
            raise ProfileValidationError(report)

        # 5. Return an EMPTY FinancialModel with report + context. No math.
        model = FinancialModel.empty()
        model.validation_report = report
        model.meta = ModelMeta(
            industry=industry_model.industry if industry_model else None,
            purpose=profile.purpose.purpose,
            currency=profile.currency,
            projection_years=profile.timeline.projection_years,
        )
        return model
