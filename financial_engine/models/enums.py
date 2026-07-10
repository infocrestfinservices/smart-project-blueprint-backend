"""
enums.py

Controlled vocabularies for the Financial Engine. Every categorical value in a
BusinessProfile / FinancialModel is expressed as one of these enums so the rest
of the engine (registries, validators, future calculation modules) can switch on
stable keys rather than free-form strings.

Pure data — no behaviour, no dependencies on the rest of the engine.
"""

from enum import Enum


class Industry(str, Enum):
    """Business industries the engine can model. Extend by adding a member here
    and registering a definition in the IndustryRegistry."""
    MANUFACTURING = "manufacturing"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    HOSPITAL = "hospital"
    RETAIL = "retail"
    SOFTWARE = "software"
    EDUCATION = "education"
    OTHER = "other"


class ReportPurpose(str, Enum):
    """Why the report is being produced. Drives which sections and model outputs
    a downstream report needs (wired up in the PurposeRegistry)."""
    FEASIBILITY_STUDY = "feasibility_study"
    CMA_DATA = "cma_data"
    IRR_ANALYSIS = "irr_analysis"
    IMMIGRATION_BUSINESS_PLAN = "immigration_business_plan"
    REAL_ESTATE = "real_estate"
    STARTUP_FUNDRAISING = "startup_sme_fundraising"
    GENERAL = "general"


class Currency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AED = "AED"
    SGD = "SGD"
    AUD = "AUD"
    CAD = "CAD"


class BusinessConstitution(str, Enum):
    PROPRIETORSHIP = "proprietorship"
    PARTNERSHIP = "partnership"
    LLP = "llp"
    PRIVATE_LIMITED = "private_limited"
    PUBLIC_LIMITED = "public_limited"
    OTHER = "other"


class FundingSourceType(str, Enum):
    EQUITY = "equity"
    TERM_LOAN = "term_loan"
    WORKING_CAPITAL_LOAN = "working_capital_loan"
    GRANT = "grant"
    SUBSIDY = "subsidy"
    OTHER = "other"


class AreaUnit(str, Enum):
    SQFT = "sqft"
    SQM = "sqm"
    ACRE = "acre"
    HECTARE = "hectare"


class DepreciationMethod(str, Enum):
    """Reserved for the Stage-2 depreciation engine."""
    STRAIGHT_LINE = "straight_line"
    WRITTEN_DOWN_VALUE = "written_down_value"


class DataSource(str, Enum):
    """Where a profile's facts came from — used for auditing/trust."""
    USER = "user"
    AI = "ai"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ValidationSeverity(str, Enum):
    ERROR = "error"      # blocks a trustworthy model
    WARNING = "warning"  # allowed, but worth surfacing
    INFO = "info"        # informational only
