"""
purpose_configs.py

THE ONE FILE YOU EDIT TO ADD A PURPOSE.

A single flat tuple of PurposeConfig literals — the complete catalogue of supported
report purposes and their orchestration metadata. Adding a purpose = adding one
PurposeConfig entry here. Nothing else in the application changes.

Aliases are declared inline on each entry (self-contained; not loaded from the AI
layer's purpose_field_extensions.json). The canonical names deliberately match the
canonical purpose names used elsewhere in the product so the two stay conceptually
aligned, but there is no import-time coupling.

STATUS OF METADATA (honest, not aspirational)
---------------------------------------------
Bank Loan is the reference implementation: every field mirrors the LIVE constants in
services/bank_loan_pipeline_service.py (template_id "bank_loan_cma", the 59-cell CMA
mapper, the DSCR viability guard). Those values are copied to match exactly, so any
future generic caller resolving "Bank Loan" reproduces today's behaviour precisely.

Every OTHER purpose has no Excel template yet, so its template_id and mapper_profile
are None on purpose. Their viability_policy / engine_profile carry declared future
NAMES — pointers to behaviour that will be implemented later, not stubs pretending to
run today. Resolving such a purpose returns valid metadata that says, in effect,
"recognised purpose, no renderable template yet."
"""

from __future__ import annotations

from .purpose_config import PurposeConfig

# Order is cosmetic (enumeration only); resolution is by name/alias, not position.
PURPOSE_CONFIGS = (
    # ── Reference implementation — mirrors the live Bank Loan pipeline constants ──
    PurposeConfig(
        canonical_name="Bank Loan",
        aliases=("bank_loan", "cma_data", "cma"),
        template_id="bank_loan_cma",          # == services/bank_loan_pipeline_service.TEMPLATE_ID
        mapper_profile="cma_59",              # the existing 44-field -> 59-cell map
        output_prefix="bank_loan",            # == slug("Bank Loan")
        viability_policy="dscr_min",          # DSCR >= 1.2 + capacity guard (lives in the pipeline)
        engine_profile="bank_cma",            # generic core + CMA/DSCR presentation
    ),

    # ── Pending purposes: recognised, extension fields defined, no template yet ──
    PurposeConfig(
        canonical_name="Feasibility Study",
        aliases=("feasibility_study", "feasibility"),
        template_id=None,
        mapper_profile=None,
        output_prefix="feasibility_study",
        viability_policy="irr_npv",
        engine_profile="feasibility",
    ),
    PurposeConfig(
        canonical_name="Government Grant",
        aliases=("government_grant", "grant"),
        template_id=None,
        mapper_profile=None,
        output_prefix="government_grant",
        viability_policy="subsidy_eligibility",
        engine_profile="grant",
    ),
    PurposeConfig(
        canonical_name="Venture Capital",
        aliases=("venture_capital", "vc"),
        template_id=None,
        mapper_profile=None,
        output_prefix="venture_capital",
        viability_policy="valuation",
        engine_profile="equity_round",
    ),
    PurposeConfig(
        canonical_name="Angel Investment",
        aliases=("angel_investment", "angel"),
        template_id=None,
        mapper_profile=None,
        output_prefix="angel_investment",
        viability_policy="valuation",
        engine_profile="equity_round",
    ),
    PurposeConfig(
        canonical_name="Immigration Business Plan",
        aliases=("immigration_business_plan", "immigration"),
        template_id=None,
        mapper_profile=None,
        output_prefix="immigration_business_plan",
        viability_policy="employment_commitment",
        engine_profile="immigration",
    ),
    PurposeConfig(
        canonical_name="Internal Business Planning",
        aliases=("internal_business_planning", "internal_planning"),
        template_id=None,
        mapper_profile=None,
        output_prefix="internal_business_planning",
        viability_policy=None,
        engine_profile="internal",
    ),
    PurposeConfig(
        canonical_name="Real Estate",
        aliases=("real_estate",),
        template_id=None,
        mapper_profile=None,
        output_prefix="real_estate",
        viability_policy="absorption",
        engine_profile="real_estate",
    ),
    PurposeConfig(
        canonical_name="Startup & SME Fundraising",
        aliases=("startup_sme_fundraising", "startup_fundraising", "startup"),
        template_id=None,
        mapper_profile=None,
        output_prefix="startup_sme_fundraising",
        viability_policy="runway",
        engine_profile="fundraising",
    ),
)
