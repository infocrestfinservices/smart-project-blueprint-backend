"""
operating_models.py

The OPERATING MODEL of each industry — what actually drives its revenue and cost,
in that industry's own vocabulary. This is the heart of industry adaptability: a
manufacturer runs on capacity × utilisation and per-unit conversion cost; a shop
runs on transactions × average bill and cost of goods; a hotel on room-nights ×
tariff; a SaaS firm on subscribers × ARPU. The arithmetic shape for every
service/trade business is the same — VOLUME × PRICE for revenue, and COST OF SALES
as a margin off revenue — so one engine computes them all; only the DRIVERS
(their names, units and benchmark bands) change per industry. Manufacturing keeps
its own capacity-based model (the frozen Bank Loan path).

Each model is pure data. Adding an industry is adding a spec here (plus, for the
workbook, an industry template) — never new calculation code. The generic
volume-price-margin engine in service_calc.py reads these specs.

Fields
------
key            : industry slug (matches the Industry enum value / folded name)
display_name   : human name (matches INDUSTRY_MAP key where one exists)
family         : "capacity" (manufacturing-style) or "volume_price" (service/trade)
volume_label   : what one unit of activity is ("Transactions / customers", "Covers
                 served", "Room-nights sold", "Active subscribers", "Patients treated")
price_label    : what the per-unit price means ("Average bill value", "Average order
                 value", "Average room tariff", "ARPU / month", "Average treatment charge")
cost_label     : the main cost of sales line ("Cost of goods sold", "Food & beverage
                 cost", "Cost of services")
margin_hint    : (low, high) typical gross-margin band for sanity checks / defaults
operational_kpis : the industry-specific KPIs a CA/analyst expects on the dashboard
stream_mix     : the four ANCILLARY revenue streams the industry template exposes
                 (Assumptions C66:C69), each as a fraction of CORE revenue
                 (volume x price). A hotel earns F&B and banquet income on top of
                 room revenue; a shop earns very little beyond the till. Used to seed
                 those cells when the AI leaves them blank, so no report ever ships
                 with an empty "Additional revenue streams" block.
default_segments : fallback target-market segments (name, share) summing to 1.0, used
                 only when the AI named none — so the segment table is never blank and
                 always ties to Net Sales.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class OperatingModel:
    key: str
    display_name: str
    family: str                      # "capacity" | "volume_price"
    volume_label: str = ""
    price_label: str = ""
    cost_label: str = "Cost of sales"
    margin_hint: Optional[Tuple[float, float]] = None
    operational_kpis: List[str] = field(default_factory=list)
    # What the two driver sheets are CALLED in this industry. A factory has a
    # "Production Plan"; a shop has a "Purchase / Inventory Plan"; a mine has an
    # "Extraction Plan". These are titles, not tab names — Excel forbids "/" in a
    # tab name, and renaming tabs would break every formula that references them.
    production_title: str = "Production Plan"
    sales_title: str = "Sales Plan"
    # Ancillary streams as a fraction of CORE revenue, in template cell order
    # C66, C67, C68, C69. Empty for the capacity family — the frozen manufacturing
    # workbook has no streams section and must never be touched.
    stream_mix: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # How many units of each stream one unit of CORE volume generates — 2.5 covers of
    # F&B per room-night, 0.8 drinks per restaurant cover, 0.5 diagnostic tests per
    # patient. Turns each stream into a real volume x price build-up (the CA format)
    # instead of a lump sum: stream volume = core volume x factor, and the price falls
    # out of stream_mix so the revenue still lands exactly on the industry profile.
    stream_vol_per_core: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    # Direct wages as a share of TOTAL revenue (core + streams) that this industry
    # actually runs at. Nothing in the pipeline ever checked period cost against
    # revenue, so the AI's wage fill landed anywhere from 1.5% to 54%; this is the
    # band reconcile_operating_costs clamps into.
    labour_pct: Optional[Tuple[float, float]] = None
    # Does this industry carry physical stock? Drives whether the workbook gets an
    # Inventory Schedule — a SaaS firm or a coaching institute showing 'finished
    # goods' would be noise, a pickle plant without one would be a gap a CA flags.
    holds_inventory: bool = False
    # (segment name, share) fallback; shares sum to 1.0.
    default_segments: Tuple[Tuple[str, float], ...] = ()


# The 17 INDUSTRY_MAP industries mapped to an operating model. Production-style
# industries (goods made from inputs via plant) use the capacity family; service and
# trade industries use volume × price with a margin-based cost of sales.
_MODELS: Dict[str, OperatingModel] = {}


def _add(m: OperatingModel):
    _MODELS[m.key] = m


# ── capacity family (goods produced via plant & machinery) ──────────────────────
_add(OperatingModel("manufacturing", "Manufacturing", "capacity",
    "Units produced", "Selling price / unit", "Cost of production",
    (0.25, 0.45), ["Capacity utilisation", "Contribution margin", "Break-even %"],
    production_title="Production Plan", sales_title="Sales Plan",
    # A factory earns more than its main line: scrap and by-product, job work on spare
    # capacity, trading of bought-out items. Modest next to the core output, but a CA
    # expects to see them. NOTE: manufacturing deliberately has NO labour_pct — its wage
    # cell is left exactly as filled, and no gross-margin clamp applies to this family.
    stream_mix=(0.040, 0.050, 0.030, 0.010),
    stream_vol_per_core=(0.05, 0.10, 0.03, 0.02),
    holds_inventory=True))
for k, name, _ptitle, _stitle in [
    ("agriculture", "Agriculture & Farming", "Production Plan", "Sales Plan"),
    ("textile", "Textile & Garments", "Production Plan", "Sales Plan"),
    ("automobile", "Automobile / Auto Ancillary", "Production Plan", "Sales Plan"),
    ("mining", "Mining & Minerals", "Extraction Plan", "Sales Plan"),
    ("renewable_energy", "Renewable Energy", "Generation Plan", "Revenue Plan"),
    ("construction", "Construction & Real Estate", "Project Execution Plan", "Revenue Plan"),
]:
    _add(OperatingModel(k, name, "capacity", "Units produced / output",
        "Realisation / unit", "Cost of production", (0.2, 0.5),
        ["Capacity utilisation", "Contribution margin", "Break-even %"],
        production_title=_ptitle, sales_title=_stitle,
        holds_inventory=(k != "renewable_energy")))

# ── volume × price family (service / trade) ─────────────────────────────────────
_add(OperatingModel("retail", "Retail & E-Commerce", "volume_price",
    "Transactions / customers", "Average bill value", "Cost of goods sold",
    (0.15, 0.35), ["Average basket size", "Inventory turnover", "Sales per sq ft"],
    production_title="Purchase / Inventory Plan", sales_title="Sales Plan",
    # A shop earns little beyond the till: services, fitting, AMC.
    stream_mix=(0.030, 0.020, 0.020, 0.010),
    stream_vol_per_core=(0.05, 0.02, 0.03, 0.02),
    labour_pct=(0.08, 0.15),
    default_segments=(("Walk-in retail customers", 0.55),
                      ("Online / marketplace buyers", 0.30),
                      ("Bulk / institutional buyers", 0.15)),
    holds_inventory=True))
_add(OperatingModel("restaurant", "Food & Beverage / Restaurant", "volume_price",
    "Covers served", "Average order value", "Food & beverage cost",
    (0.60, 0.72), ["Food cost %", "Table turnover", "Average order value"],
    production_title="Operations Plan", sales_title="Revenue Plan",
    # Bar/beverages is the classic margin engine on top of covers.
    stream_mix=(0.120, 0.070, 0.040, 0.020),
    stream_vol_per_core=(0.8, 0.01, 0.15, 0.1),
    labour_pct=(0.25, 0.35),
    default_segments=(("Dine-in guests", 0.60),
                      ("Takeaway & delivery", 0.28),
                      ("Catering & events", 0.12)),
    holds_inventory=True))
_add(OperatingModel("hotel", "Tourism & Hospitality", "volume_price",
    "Room-nights sold", "Average room tariff (ARR)", "Cost of services",
    (0.55, 0.75), ["Occupancy rate", "ADR", "RevPAR"],
    production_title="Operations Plan", sales_title="Revenue Plan",
    # F&B is typically a quarter to a third of a full-service hotel's revenue.
    stream_mix=(0.200, 0.070, 0.050, 0.030),
    stream_vol_per_core=(2.5, 0.01, 0.005, 1.0),
    labour_pct=(0.22, 0.33),
    default_segments=(("Leisure travellers", 0.50),
                      ("Corporate & MICE clients", 0.32),
                      ("Group & event bookings", 0.18)),
    holds_inventory=True))
_add(OperatingModel("software", "Technology & Software", "volume_price",
    "Active subscribers", "ARPU (per subscriber / year)", "Cost of revenue (hosting, support)",
    (0.70, 0.85), ["MRR / ARR", "Churn rate", "CAC", "LTV"],
    production_title="Service Delivery Plan", sales_title="Revenue Plan",
    # Onboarding + services + AMC around a subscription base.
    stream_mix=(0.100, 0.080, 0.050, 0.020),
    stream_vol_per_core=(0.3, 0.05, 0.4, 0.1),
    labour_pct=(0.35, 0.5),
    default_segments=(("SMB subscribers", 0.45),
                      ("Enterprise accounts", 0.40),
                      ("Individual / self-serve users", 0.15)),
    holds_inventory=False))
_add(OperatingModel("hospital", "Healthcare & Pharma", "volume_price",
    "Patients treated (OPD/IPD)", "Average treatment charge", "Cost of medical services",
    (0.40, 0.60), ["Bed occupancy", "Revenue per bed", "Average length of stay"],
    production_title="Service Delivery Plan", sales_title="Revenue Plan",
    # Pharmacy and diagnostics are major ancillary earners in a hospital.
    stream_mix=(0.180, 0.120, 0.080, 0.020),
    stream_vol_per_core=(0.15, 0.8, 0.5, 0.1),
    labour_pct=(0.25, 0.4),
    default_segments=(("OPD patients", 0.45),
                      ("IPD / inpatients", 0.40),
                      ("Insurance & corporate tie-ups", 0.15)),
    holds_inventory=True))
_add(OperatingModel("education", "Education & Training", "volume_price",
    "Students enrolled", "Fee per student (year)", "Cost of delivery",
    (0.45, 0.65), ["Enrolment / capacity", "Fee realisation", "Cost per student"],
    production_title="Academic Operations Plan", sales_title="Revenue Plan",
    stream_mix=(0.080, 0.060, 0.040, 0.020),
    stream_vol_per_core=(0.6, 1.0, 0.3, 0.2),
    labour_pct=(0.4, 0.55),
    default_segments=(("Regular full-time students", 0.55),
                      ("Working professionals / part-time", 0.30),
                      ("Corporate & institutional training", 0.15)),
    holds_inventory=False))
_add(OperatingModel("trading", "Import / Export Trading", "volume_price",
    "Units traded", "Realisation / unit", "Cost of goods traded",
    (0.08, 0.20), ["Gross margin %", "Stock turnover", "Order cycle"],
    production_title="Trading Plan", sales_title="Revenue Plan",
    # Thin-margin business; ancillary income is correspondingly small.
    stream_mix=(0.050, 0.020, 0.020, 0.010),
    stream_vol_per_core=(1.0, 0.2, 0.5, 0.1),
    labour_pct=(0.02, 0.06),
    default_segments=(("Domestic wholesale buyers", 0.50),
                      ("Export clients", 0.35),
                      ("Retail / small orders", 0.15)),
    holds_inventory=True))
_add(OperatingModel("transport", "Transportation & Logistics", "volume_price",
    "Trips / consignments", "Revenue per trip", "Operating cost of services",
    (0.25, 0.45), ["Fleet utilisation", "Cost per km", "Load factor"],
    production_title="Fleet Operations Plan", sales_title="Revenue Plan",
    stream_mix=(0.080, 0.050, 0.040, 0.010),
    stream_vol_per_core=(0.3, 0.2, 0.15, 0.05),
    labour_pct=(0.2, 0.3),
    default_segments=(("Contract / corporate clients", 0.55),
                      ("Spot-market consignments", 0.30),
                      ("E-commerce & last-mile", 0.15)),
    holds_inventory=False))
_add(OperatingModel("media", "Media & Entertainment", "volume_price",
    "Units sold / subscribers", "Average revenue per unit", "Cost of content / services",
    (0.35, 0.60), ["Subscribers", "ARPU", "Content cost %"],
    production_title="Operations Plan", sales_title="Revenue Plan",
    # Advertising typically rivals subscription income.
    stream_mix=(0.150, 0.080, 0.050, 0.020),
    stream_vol_per_core=(1.0, 0.02, 0.005, 0.05),
    labour_pct=(0.25, 0.35),
    default_segments=(("Advertisers & sponsors", 0.45),
                      ("Subscribers / viewers", 0.40),
                      ("Licensing partners", 0.15)),
    holds_inventory=False))
_add(OperatingModel("other", "General Business", "volume_price",
    "Units of activity", "Average price / unit", "Cost of sales",
    (0.30, 0.50), ["Gross margin %", "Asset turnover"],
    production_title="Operations Plan", sales_title="Revenue Plan",
    stream_mix=(0.040, 0.030, 0.020, 0.010),
    stream_vol_per_core=(0.2, 0.15, 0.1, 0.05),
    labour_pct=(0.15, 0.25),
    default_segments=(("Primary customer segment", 0.55),
                      ("Secondary customer segment", 0.30),
                      ("Other customers", 0.15)),
    holds_inventory=True))


def _fold(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s or "").casefold())


# folded lookup over both slug and display name, so "Retail & E-Commerce", "retail"
# and "retailecommerce" all resolve.
_INDEX: Dict[str, OperatingModel] = {}
for _m in _MODELS.values():
    _INDEX[_fold(_m.key)] = _m
    _INDEX[_fold(_m.display_name)] = _m
# a few common aliases
for _alias, _slug in [("ecommerce", "retail"), ("saas", "software"), ("tech", "software"),
                      ("hospitality", "hotel"), ("healthcare", "hospital"),
                      ("fnb", "restaurant"), ("foodbeverage", "restaurant"),
                      # Processing/production businesses are MANUFACTURING, not
                      # restaurants — "Food Processing" was matching the F&B row and
                      # relabelling a chips plant with "covers served".
                      ("foodprocessing", "manufacturing"),
                      ("agroprocessing", "manufacturing"),
                      ("foodmanufacturing", "manufacturing"),
                      ("fmcg", "manufacturing"), ("packaging", "manufacturing"),
                      ("engineering", "manufacturing"), ("pharma", "hospital"),
                      ("logistics", "transport"), ("ecommercelogistics", "transport"),
                      ("realestate", "construction"), ("infrastructure", "construction"),
                      ("solar", "renewable_energy"), ("energy", "renewable_energy"),
                      # EdTech / e-learning is education DELIVERY (volume-price), not a
                      # factory — without this it fell through to the manufacturing base.
                      ("educationtechnology", "education"), ("edtech", "education"),
                      ("elearning", "education"), ("onlineeducation", "education"),
                      ("onlinelearning", "education")]:
    if _slug in _MODELS:
        _INDEX.setdefault(_alias, _MODELS[_slug])


def get_operating_model(industry_type) -> Optional[OperatingModel]:
    """The operating model for an industry name/slug, or None if unknown."""
    if not industry_type:
        return None
    return _INDEX.get(_fold(industry_type))


def family_of(industry_type) -> str:
    """"capacity", "volume_price", or "" when unknown (caller falls back to manufacturing)."""
    m = get_operating_model(industry_type)
    return m.family if m else ""


def all_models() -> List[OperatingModel]:
    return list(_MODELS.values())
