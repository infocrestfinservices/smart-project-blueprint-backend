"""
purpose_config.py

The PurposeConfig value object: immutable orchestration metadata for one report
purpose. This is the APPLICATION layer's view of a purpose — which template to fill,
which mapper profile to use, which viability policy and calculation engine will run,
and how the output file is named.

It is deliberately inert. It holds ONLY strings and tuples of strings. It performs no
calculation, no AI, no Excel, no service work. Fields named `*_policy` / `*_profile`
are NAMES that point at behaviour living elsewhere; resolving a name to an actual
object is a separate concern, never this object's job.

Kept independent from financial_engine/registry/purpose_registry.py (which wires the
financial engine's output sections) — that is a different concern. This package is the
orchestration/config layer and must not depend on the engine or the AI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class PurposeConfig:
    """Immutable configuration for a single report purpose.

    Frozen (immutable + hashable), so a config can be shared freely and can never be
    mutated by a caller. Composition only — no base class, no behaviour beyond the
    read-only alias helper below.

    Fields
    ------
    canonical_name   The one true display name, e.g. "Bank Loan". Also the key the
                     registry indexes by.
    aliases          Every other string a caller might pass for this purpose
                     (slugs, legacy ids). Self-contained here — NOT loaded from any
                     AI-layer file — so the registry stays decoupled.
    template_id      The Excel template id this purpose fills, or None when no
                     template exists yet (honest "not renderable yet" metadata).
    mapper_profile   Names the field->cell mapping to use, or None when pending.
    output_prefix    Purpose slug used in the generated filename.
    viability_policy A NAME pointing at the viability check run for this purpose
                     (e.g. Bank Loan's DSCR floor). None when there is none.
    engine_profile   A NAME pointing at the calculation engine/profile a purpose
                     will use. None when pending.
    """

    canonical_name: str
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    template_id: Optional[str] = None
    mapper_profile: Optional[str] = None
    output_prefix: Optional[str] = None
    viability_policy: Optional[str] = None
    engine_profile: Optional[str] = None

    def matches(self, normalized: str) -> bool:
        """True if `normalized` (an already-slugified string) equals this config's
        canonical name or any alias, both slugified. Pure comparison — no lookups,
        no side effects. The registry uses this to build its alias index."""
        return normalized in self._normalized_keys()

    def _normalized_keys(self) -> Tuple[str, ...]:
        from .purpose_config_registry import normalize  # local import avoids cycle
        return tuple(normalize(k) for k in (self.canonical_name, *self.aliases))
