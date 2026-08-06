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
    and registering a definition in the IndustryRegistry.

    The canonical list is the one users actually pick from: the 17 keys of the live
    workbook's INDUSTRY_MAP (Assumptions!$S$5:$S$40), which drive its dropdown and
    every industry-dependent label. Each member's human-facing name is the matching
    INDUSTRY_MAP key, carried on the industry profile as `display_name` rather than
    duplicated here — profiles are the one place an industry is described.

    Member VALUES are deliberately unchanged from the original eight, so existing
    profiles/tests keep resolving; only the human-facing names widened (e.g. HOTEL
    covers "Tourism & Hospitality", HOSPITAL covers "Healthcare & Pharma").
    """
    MANUFACTURING = "manufacturing"          # Manufacturing
    RESTAURANT = "restaurant"                # Food & Beverage / Restaurant
    HOTEL = "hotel"                          # Tourism & Hospitality
    HOSPITAL = "hospital"                    # Healthcare & Pharma
    RETAIL = "retail"                        # Retail & E-Commerce
    SOFTWARE = "software"                    # Technology & Software
    EDUCATION = "education"                  # Education & Training
    OTHER = "other"                          # General Business
    AGRICULTURE = "agriculture"              # Agriculture & Farming
    RENEWABLE_ENERGY = "renewable_energy"    # Renewable Energy
    CONSTRUCTION = "construction"            # Construction & Real Estate
    TRANSPORT = "transport"                  # Transportation & Logistics
    TEXTILE = "textile"                      # Textile & Garments
    AUTOMOBILE = "automobile"                # Automobile / Auto Ancillary
    TRADING = "trading"                      # Import / Export Trading
    MEDIA = "media"                          # Media & Entertainment
    MINING = "mining"                        # Mining & Minerals


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
