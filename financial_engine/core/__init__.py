"""
financial_engine.core

The engine that ties the models, registries and validators together. Stage 1
exposes the FinancialEngine skeleton only — no calculations.
"""

from .engine import FinancialEngine, ProfileValidationError

__all__ = ["FinancialEngine", "ProfileValidationError"]
