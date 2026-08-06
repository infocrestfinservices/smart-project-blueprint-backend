"""
generic_pipeline_service.py

Generic, configuration-driven report orchestration.

    purpose ─▶ Purpose Catalog ─▶ PurposeConfig ─▶ Generic Pipeline ─▶ executor

This layer is an ORCHESTRATOR ONLY. It contains:

  * NO financial calculations
  * NO AI / prompt logic
  * NO Excel / mapping / template logic
  * NO purpose-specific constants (TEMPLATE_ID, mapper profile, output naming,
    engine selection, viability policy)
  * NO `if purpose == ...` chains

Everything purpose-specific is read from the PurposeConfig resolved out of the
Purpose Catalog, and execution is dispatched through a registry keyed by the
config's engine_profile (Strategy pattern via a dict — composition, not branching).

BANK LOAN IS THE FIRST REGISTERED CONFIGURATION.
Its executor delegates VERBATIM to the existing services/bank_loan_pipeline_service.
run_bank_loan_pipeline — same function, same arguments, same returned dict. Nothing
about Bank Loan's assumptions, mapping, template, recalculation, DSCR, ratios,
filenames, or API response changes: this module never reimplements or wraps that
pipeline's behaviour, it only routes to it. The Bank Loan pipeline's own DSCR /
capacity / working-capital logic IS its viability policy and engine — retained
exactly as-is by calling it unmodified.

Adding a future purpose (Feasibility, VC, Grant, ...) requires: a PurposeConfig entry
(already in purpose_catalog) + an executor registered under its engine_profile. The
generic pipeline itself never changes. Until an executor is registered, a recognised
purpose returns a structured "not_implemented" result — never a Bank Loan fallback.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

from purpose_catalog import PurposeConfig, resolve_purpose
from services.bank_loan_pipeline_service import run_bank_loan_pipeline

logger = logging.getLogger("generic_pipeline")

# An executor runs one purpose end-to-end. Signature is uniform so the registry can
# dispatch without knowing which purpose it is calling.
Executor = Callable[[str, str, str, PurposeConfig], dict]


def _bank_loan_executor(industry: str, purpose: str, user_details: str,
                        config: PurposeConfig) -> dict:
    """Bank Loan execution = the EXISTING pipeline, called verbatim.

    The original `purpose` string is forwarded unchanged (so the filename slug and the
    AI prompt are identical to today). `config` is intentionally unused here: Bank
    Loan's template, mapper, engine and viability policy already live inside the
    existing pipeline, which must not be modified. This adapter adds nothing and
    subtracts nothing — it is a pass-through so Bank Loan output stays byte-identical.
    """
    return run_bank_loan_pipeline(industry, purpose, user_details)


# Registry keyed by PurposeConfig.engine_profile. Composition, not inheritance; a dict
# lookup, not an if/elif chain. Exactly one entry today: Bank Loan.
EXECUTOR_REGISTRY: Dict[str, Executor] = {
    "bank_cma": _bank_loan_executor,
}


def run_report_pipeline(
    industry: str,
    purpose: str,
    user_details: str,
    *,
    resolver: Callable[[str], Optional[PurposeConfig]] = resolve_purpose,
    executors: Optional[Dict[str, Executor]] = None,
) -> dict:
    """Resolve `purpose` through the Purpose Catalog and dispatch to its executor.

    `resolver` and `executors` are injectable (Dependency Inversion) with production
    defaults, so tests can drive the pipeline without the real catalog or a real
    executor.

    Returns:
      * whatever the purpose's executor returns (for Bank Loan: the existing
        pipeline's dict, VERBATIM);
      * {"status": "unknown_purpose", ...}  if the string is not in the catalog;
      * {"status": "not_implemented", ...}   if recognised but no executor is
        registered yet — carrying that purpose's own metadata, never Bank Loan's.
    """
    registry = EXECUTOR_REGISTRY if executors is None else executors

    config = resolver(purpose)
    if config is None:
        logger.info("generic pipeline: unrecognised purpose %r", purpose)
        return {
            "status": "unknown_purpose",
            "purpose": purpose,
            "reason": "Purpose is not registered in the Purpose Catalog.",
        }

    executor = registry.get(config.engine_profile)
    if executor is None:
        logger.info("generic pipeline: purpose %r recognised but no executor for "
                    "engine_profile %r", config.canonical_name, config.engine_profile)
        return {
            "status": "not_implemented",
            "purpose": config.canonical_name,
            "template_id": config.template_id,
            "mapper_profile": config.mapper_profile,
            "engine_profile": config.engine_profile,
            "viability_policy": config.viability_policy,
            "output_prefix": config.output_prefix,
            "reason": "Purpose recognized but its execution pipeline "
                      "has not been implemented yet.",
        }

    logger.info("generic pipeline: dispatching %r via engine_profile %r",
                config.canonical_name, config.engine_profile)
    return executor(industry, purpose, user_details, config)
