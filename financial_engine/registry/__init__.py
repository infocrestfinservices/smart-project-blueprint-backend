"""
financial_engine.registry

Registration-based catalogues of industries and report purposes. The engine
resolves behaviour by lookup here rather than hardcoded branching, so new
industries/purposes are added by registration alone.
"""

from .industry_registry import (
    IndustryAlreadyRegistered,
    IndustryNotRegistered,
    IndustryRegistry,
    industry_registry,
)
from .purpose_registry import (
    PurposeAlreadyRegistered,
    PurposeDefinition,
    PurposeNotRegistered,
    PurposeRegistry,
    purpose_registry,
)

__all__ = [
    "IndustryRegistry",
    "IndustryNotRegistered",
    "IndustryAlreadyRegistered",
    "industry_registry",
    "PurposeRegistry",
    "PurposeDefinition",
    "PurposeNotRegistered",
    "PurposeAlreadyRegistered",
    "purpose_registry",
]
