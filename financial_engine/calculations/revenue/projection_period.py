"""
projection_period.py

Reusable time structures shared by EVERY calculation engine (revenue, expenses,
payroll, loans, cash flow, …) so no engine reinvents "a value per year".

    ProjectionPeriod   — one year in the projection (index, label, fiscal year)
    ProjectionTimeline — the ordered set of periods (Year 1..N)
    YearlySeries       — a value per period, with element-wise arithmetic and
                         growth helpers

These are pure value objects — deterministic, no calculations of any business
meaning, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple, Union

Number = Union[int, float]


@dataclass(frozen=True)
class ProjectionPeriod:
    """A single year in the projection."""
    index: int                       # 1-based year number (Year 1 == 1)
    label: str                       # e.g. "Year 1 (FY2025)"
    fiscal_year: Optional[int] = None


@dataclass(frozen=True)
class ProjectionTimeline:
    """The ordered projection horizon. Built once and reused by every engine."""
    periods: Tuple[ProjectionPeriod, ...]

    @classmethod
    def of_years(cls, years: int, start_year: Optional[int] = None) -> "ProjectionTimeline":
        years = max(1, int(years))
        out: List[ProjectionPeriod] = []
        for i in range(1, years + 1):
            fy = (int(start_year) + i - 1) if start_year else None
            label = f"Year {i}" + (f" (FY{fy})" if fy else "")
            out.append(ProjectionPeriod(index=i, label=label, fiscal_year=fy))
        return cls(periods=tuple(out))

    @property
    def years(self) -> int:
        return len(self.periods)

    def indices(self) -> List[int]:
        return [p.index for p in self.periods]

    def labels(self) -> List[str]:
        return [p.label for p in self.periods]

    def __iter__(self):
        return iter(self.periods)

    def __len__(self) -> int:
        return len(self.periods)

    def __getitem__(self, i: int) -> ProjectionPeriod:
        return self.periods[i]


@dataclass
class YearlySeries:
    """A value for each projection year. Index 0 == Year 1.

    Provides the small, deterministic vector operations engines need so yearly
    maths reads clearly (production = capacity × utilisation) instead of ad-hoc
    loops scattered around the codebase.
    """
    points: List[float] = field(default_factory=list)

    # -- constructors -------------------------------------------------------
    @classmethod
    def zeros(cls, n: int) -> "YearlySeries":
        return cls([0.0] * max(0, int(n)))

    @classmethod
    def constant(cls, value: Number, n: int) -> "YearlySeries":
        return cls([float(value)] * max(0, int(n)))

    @classmethod
    def from_mapping(cls, mapping: Dict[int, Number], n: int,
                     default: Number = 0.0, hold_last: bool = False) -> "YearlySeries":
        """Build an n-point series from a 1-based {year: value} mapping. With
        hold_last, years past the last supplied value carry it forward."""
        pts: List[float] = []
        last = float(default)
        for i in range(1, int(n) + 1):
            if i in mapping and mapping[i] is not None:
                last = float(mapping[i])
                pts.append(last)
            else:
                pts.append(last if hold_last else float(default))
        return cls(pts)

    @classmethod
    def sum(cls, series_list: Iterable["YearlySeries"], n: Optional[int] = None) -> "YearlySeries":
        items = list(series_list)
        if not items:
            return cls.zeros(n or 0)
        length = n if n is not None else len(items[0])
        return cls([float(sum(s.points[i] for s in items if i < len(s.points)))
                    for i in range(length)])

    # -- access -------------------------------------------------------------
    def year(self, n: int) -> float:
        """Value for 1-based year n (Year 1 == n=1)."""
        return self.points[n - 1]

    def as_list(self) -> List[float]:
        return list(self.points)

    def total(self) -> float:
        return float(sum(self.points))

    # -- element-wise arithmetic -------------------------------------------
    def multiply(self, other: Union["YearlySeries", Number]) -> "YearlySeries":
        if isinstance(other, YearlySeries):
            return YearlySeries([a * b for a, b in zip(self.points, other.points)])
        return YearlySeries([a * float(other) for a in self.points])

    def scale(self, factor: Number) -> "YearlySeries":
        return self.multiply(factor)

    def map(self, fn) -> "YearlySeries":
        return YearlySeries([fn(v) for v in self.points])

    # -- growth -------------------------------------------------------------
    def yoy_growth(self) -> List[Optional[float]]:
        """Year-on-year growth as fractions. Year 1 is None (no prior year)."""
        out: List[Optional[float]] = [None]
        for i in range(1, len(self.points)):
            prev = self.points[i - 1]
            out.append((self.points[i] / prev - 1.0) if prev not in (0, 0.0) else None)
        return out

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self):
        return iter(self.points)
