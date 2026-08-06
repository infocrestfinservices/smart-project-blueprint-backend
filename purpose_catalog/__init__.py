"""
purpose_catalog — application-layer orchestration configuration for report purposes.

Public surface: the Purpose Config Registry, which resolves a report-purpose string
into its immutable PurposeConfig (template id, mapper profile, viability policy,
engine profile, output prefix). Metadata only — no AI, calculation, Excel, or service
logic.

Completely additive and self-contained. It imports nothing from the app's settings
(config.py), the existing purpose_config.py generation module, the Assumption
Architect, the mapper, the financial engine, or the Bank Loan pipeline. It is also
distinct from financial_engine/registry/purpose_registry.py, which wires the financial
engine's output sections — a different concern.

The package is named `purpose_catalog` specifically to avoid colliding with the two
existing top-level modules `config.py` and `purpose_config.py`.
"""

from .purpose_config import PurposeConfig
from .purpose_config_registry import (
    PurposeConfigRegistry,
    purpose_config_registry,
    resolve_purpose,
    get_purpose_config,
    all_purposes,
    normalize,
)

__all__ = [
    "PurposeConfig",
    "PurposeConfigRegistry",
    "purpose_config_registry",
    "resolve_purpose",
    "get_purpose_config",
    "all_purposes",
    "normalize",
]
