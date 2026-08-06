"""
purpose_config_registry.py

The Purpose Config Registry: resolves a purpose string (any casing, any declared
alias) into its immutable PurposeConfig. Metadata resolution ONLY.

  - No AI logic, no calculation, no Excel, no service calls.
  - No if/elif chains — resolution is a single dict lookup over a pre-built index.
  - Composition, not inheritance: the registry HOLDS configs; it is not a base class.
  - Self-contained: aliases come from the PurposeConfig entries themselves, never
    from any AI-layer file, so this layer is decoupled from the Assumption Architect.

Independent from financial_engine/registry/purpose_registry.py, which is a different
concern (financial-engine section wiring). This one is application/orchestration
config.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from .purpose_config import PurposeConfig
from .purpose_configs import PURPOSE_CONFIGS


def normalize(value: str) -> str:
    """Slugify a purpose string for case/spacing/punctuation-insensitive matching:
    'Bank Loan' / 'bank-loan' / 'BANK_LOAN' all -> 'bank_loan'. Pure function."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


class DuplicatePurposeKey(Exception):
    """Two configs claim the same canonical name or alias — a catalogue error."""


class PurposeConfigRegistry:
    """Dict-backed, keyed by normalized canonical name; plus a normalized alias index.
    Built once from a tuple of PurposeConfig; resolution is O(1) lookup, no branching."""

    def __init__(self, configs: Tuple[PurposeConfig, ...] = PURPOSE_CONFIGS) -> None:
        self._by_canonical: Dict[str, PurposeConfig] = {}
        self._alias_index: Dict[str, PurposeConfig] = {}
        for config in configs:
            self._register(config)

    def _register(self, config: PurposeConfig) -> None:
        canonical = normalize(config.canonical_name)
        if canonical in self._by_canonical:
            raise DuplicatePurposeKey(
                f"Duplicate canonical purpose: {config.canonical_name!r}")
        self._by_canonical[canonical] = config
        # Every canonical + alias maps to this config in one flat index -> no if/elif
        # at resolve time. A collision across purposes is a hard catalogue error.
        for key in (config.canonical_name, *config.aliases):
            slug = normalize(key)
            existing = self._alias_index.get(slug)
            if existing is not None and existing is not config:
                raise DuplicatePurposeKey(
                    f"Alias {key!r} (->{slug!r}) claimed by both "
                    f"{existing.canonical_name!r} and {config.canonical_name!r}")
            self._alias_index[slug] = config

    # -- public API ---------------------------------------------------------
    def resolve(self, purpose: str) -> Optional[PurposeConfig]:
        """The purpose's config, or None if unrecognised. Accepts the canonical name
        or any declared alias, case/punctuation-insensitively. Pure lookup."""
        return self._alias_index.get(normalize(purpose))

    def get(self, purpose: str) -> PurposeConfig:
        """Like resolve(), but raises KeyError for an unknown purpose (for callers
        that treat an unknown purpose as a programming error rather than a branch)."""
        config = self.resolve(purpose)
        if config is None:
            raise KeyError(f"No purpose configuration for: {purpose!r}")
        return config

    def is_registered(self, purpose: str) -> bool:
        return normalize(purpose) in self._alias_index

    def all_configs(self) -> Tuple[PurposeConfig, ...]:
        return tuple(self._by_canonical.values())

    def canonical_names(self) -> Tuple[str, ...]:
        return tuple(c.canonical_name for c in self._by_canonical.values())

    def __contains__(self, purpose: str) -> bool:
        return self.is_registered(purpose)

    def __len__(self) -> int:
        return len(self._by_canonical)


# Module-level singleton — the default registry the application resolves against.
purpose_config_registry = PurposeConfigRegistry()


# -- module-level convenience API ------------------------------------------
def resolve_purpose(purpose: str) -> Optional[PurposeConfig]:
    """The config for a purpose, or None if unrecognised."""
    return purpose_config_registry.resolve(purpose)


def get_purpose_config(purpose: str) -> PurposeConfig:
    """The config for a purpose; raises KeyError if unrecognised."""
    return purpose_config_registry.get(purpose)


def all_purposes() -> Tuple[PurposeConfig, ...]:
    """Every registered purpose config."""
    return purpose_config_registry.all_configs()
