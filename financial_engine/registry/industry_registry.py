"""
industry_registry.py

A registration-based catalogue of INDUSTRY MODELS. As of Stage 2A the registry
returns a BaseIndustryModel instance (not simple metadata): the engine looks the
industry up here and works through the model's contract, never branching on the
industry with if/else. New industries plug in by registering their model — no
change anywhere else.

Only concrete models are registered. Industries whose model has not been built
yet simply resolve to None (get_or_none), which the engine surfaces as a warning.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..industry_models.base import BaseIndustryModel
from ..industry_models.manufacturing import ManufacturingModel
from ..models.enums import Industry


class IndustryAlreadyRegistered(Exception):
    pass


class IndustryNotRegistered(KeyError):
    pass


class IndustryRegistry:
    """Ordered, dict-backed registry keyed by the Industry enum, holding one
    BaseIndustryModel instance per registered industry."""

    def __init__(self) -> None:
        self._models: Dict[Industry, BaseIndustryModel] = {}

    def register(self, model: BaseIndustryModel) -> BaseIndustryModel:
        if model.industry is None:
            raise ValueError(f"{type(model).__name__} does not declare an `industry`.")
        if model.industry in self._models:
            raise IndustryAlreadyRegistered(
                f"Industry model already registered: {model.industry.value}")
        self._models[model.industry] = model
        return model

    def get(self, industry: Industry) -> BaseIndustryModel:
        try:
            return self._models[industry]
        except KeyError:
            raise IndustryNotRegistered(
                f"No industry model registered for: {industry}") from None

    def get_or_none(self, industry: Optional[Industry]) -> Optional[BaseIndustryModel]:
        if industry is None:
            return None
        return self._models.get(industry)

    def is_registered(self, industry: Industry) -> bool:
        return industry in self._models

    def all(self) -> List[BaseIndustryModel]:
        return list(self._models.values())

    def industries(self) -> List[Industry]:
        return list(self._models.keys())

    def __contains__(self, industry: Industry) -> bool:
        return industry in self._models

    def __len__(self) -> int:
        return len(self._models)


def _register_defaults(registry: IndustryRegistry) -> None:
    """Register the industry models that have concrete implementations.
    Add a line here as each new industry model is built."""
    registry.register(ManufacturingModel())


# Module-level singleton the engine uses by default.
industry_registry = IndustryRegistry()
_register_defaults(industry_registry)
