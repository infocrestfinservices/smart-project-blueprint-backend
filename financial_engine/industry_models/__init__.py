"""
financial_engine.industry_models

The Industry Modeling Framework: an abstract BaseIndustryModel contract plus the
concrete industry models that plug into the IndustryRegistry. Each model
DESCRIBES its industry (inputs, drivers, benchmark assumptions, validation);
none performs financial calculations in Stage 2A.
"""

from .base import (
    BaseIndustryModel,
    DriverCategory,
    DriverDefinition,
    FieldType,
    InputField,
)
from .manufacturing import ManufacturingModel

__all__ = [
    "BaseIndustryModel",
    "InputField",
    "DriverDefinition",
    "FieldType",
    "DriverCategory",
    "ManufacturingModel",
]
