"""
purpose_registry.py

Registration-based catalogue of report purposes. Mirrors the IndustryRegistry:
the engine looks a purpose up here instead of branching on it. Each entry
declares (for future stages) which profile sections a purpose needs and which
FinancialModel sections its report will consume.

Stage 1: the required/emitted section lists are illustrative placeholders and
carry no behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models.enums import ReportPurpose


class PurposeAlreadyRegistered(Exception):
    pass


class PurposeNotRegistered(KeyError):
    pass


@dataclass
class PurposeDefinition:
    purpose: ReportPurpose
    display_name: str
    description: str = ""
    # Placeholders for Stage 2 wiring.
    required_profile_sections: Tuple[str, ...] = ()
    model_sections: Tuple[str, ...] = ()


class PurposeRegistry:
    def __init__(self) -> None:
        self._items: Dict[ReportPurpose, PurposeDefinition] = {}

    def register(self, definition: PurposeDefinition) -> PurposeDefinition:
        if definition.purpose in self._items:
            raise PurposeAlreadyRegistered(
                f"Purpose already registered: {definition.purpose.value}")
        self._items[definition.purpose] = definition
        return definition

    def register_purpose(self, purpose: ReportPurpose, display_name: str,
                         **kwargs) -> PurposeDefinition:
        return self.register(PurposeDefinition(
            purpose=purpose, display_name=display_name, **kwargs))

    def get(self, purpose: ReportPurpose) -> PurposeDefinition:
        try:
            return self._items[purpose]
        except KeyError:
            raise PurposeNotRegistered(f"No purpose registered for: {purpose}") from None

    def get_or_none(self, purpose: Optional[ReportPurpose]) -> Optional[PurposeDefinition]:
        if purpose is None:
            return None
        return self._items.get(purpose)

    def is_registered(self, purpose: ReportPurpose) -> bool:
        return purpose in self._items

    def all(self) -> List[PurposeDefinition]:
        return list(self._items.values())

    def __contains__(self, purpose: ReportPurpose) -> bool:
        return purpose in self._items

    def __len__(self) -> int:
        return len(self._items)


def _register_defaults(registry: PurposeRegistry) -> None:
    registry.register_purpose(ReportPurpose.FEASIBILITY_STUDY, "Feasibility Study")
    registry.register_purpose(ReportPurpose.CMA_DATA, "CMA Data (Bank Loan)")
    registry.register_purpose(ReportPurpose.IRR_ANALYSIS, "IRR Analysis")
    registry.register_purpose(ReportPurpose.IMMIGRATION_BUSINESS_PLAN, "Immigration Business Plan")
    registry.register_purpose(ReportPurpose.REAL_ESTATE, "Real Estate Model")
    registry.register_purpose(ReportPurpose.STARTUP_FUNDRAISING, "Startup & SME Fundraising")
    registry.register_purpose(ReportPurpose.GENERAL, "General Business Report")


purpose_registry = PurposeRegistry()
_register_defaults(purpose_registry)
