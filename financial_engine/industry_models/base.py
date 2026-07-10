"""
base.py

The Industry Modeling Framework contract. Every industry the engine can model
provides a concrete subclass of BaseIndustryModel that *describes* — but never
calculates — how that industry behaves:

    required_inputs()      what facts the industry needs from the user/profile
    financial_drivers()    the levers that will drive the (future) calculations
    default_assumptions()  benchmark defaults for the industry
    validate_profile()     industry-specific integrity checks

Stage 2A is description only. No revenue, cost, payroll, loan, tax, or any other
financial calculation lives here or in any subclass — those arrive in Stage 2B+
and plug into these same driver definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, List, Optional

from ..models.assumptions import Assumptions
from ..models.business_profile import BusinessProfile
from ..models.enums import Industry
from ..models.financial_model import ValidationReport


class FieldType(str, Enum):
    """Data type of a required input, for the UI/AI layer to render & collect."""
    NUMBER = "number"
    INTEGER = "integer"
    PERCENT = "percent"
    CURRENCY = "currency"
    DAYS = "days"
    TEXT = "text"
    BOOLEAN = "boolean"
    ENUM = "enum"


class DriverCategory(str, Enum):
    """Groups a financial driver so downstream engines / dashboards can organise
    them consistently across industries."""
    CAPACITY = "capacity"
    PRICING = "pricing"
    COST_STRUCTURE = "cost_structure"
    WORKING_CAPITAL = "working_capital"
    OPERATIONS = "operations"
    FINANCING = "financing"


@dataclass(frozen=True)
class InputField:
    """A fact the industry needs. `profile_path` says where it maps onto a
    BusinessProfile so the collection layer knows where to store it."""
    key: str
    label: str
    field_type: FieldType
    unit: Optional[str] = None
    required: bool = True
    profile_path: Optional[str] = None
    description: str = ""


@dataclass(frozen=True)
class DriverDefinition:
    """A modelling lever for the industry. `benchmark` is a static industry
    default (data, not a calculation) that Stage-2 engines may fall back to."""
    key: str
    label: str
    category: DriverCategory
    unit: Optional[str] = None
    benchmark: Optional[float] = None
    description: str = ""


class BaseIndustryModel(ABC):
    """Abstract contract every industry model implements. Subclasses set the two
    class attributes and implement the four methods below."""

    #: The Industry enum this model serves. Concrete subclasses MUST set it.
    industry: ClassVar[Optional[Industry]] = None
    #: Human-readable name.
    display_name: ClassVar[str] = ""

    # -- contract -----------------------------------------------------------
    @abstractmethod
    def required_inputs(self) -> List[InputField]:
        """The facts this industry needs collected from the user / AI."""
        raise NotImplementedError

    @abstractmethod
    def financial_drivers(self) -> List[DriverDefinition]:
        """The levers that will drive this industry's (future) calculations."""
        raise NotImplementedError

    @abstractmethod
    def default_assumptions(self) -> Assumptions:
        """Benchmark default assumptions for this industry (static data)."""
        raise NotImplementedError

    @abstractmethod
    def validate_profile(self, profile: BusinessProfile) -> ValidationReport:
        """Industry-specific integrity checks on the input facts. No math."""
        raise NotImplementedError

    # -- convenience (non-abstract) ----------------------------------------
    def input_keys(self) -> List[str]:
        return [f.key for f in self.required_inputs()]

    def driver_keys(self) -> List[str]:
        return [d.key for d in self.financial_drivers()]

    def get_driver(self, key: str) -> Optional[DriverDefinition]:
        for d in self.financial_drivers():
            if d.key == key:
                return d
        return None

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        ind = self.industry.value if self.industry else "?"
        return f"<IndustryModel {ind} ({self.display_name})>"
