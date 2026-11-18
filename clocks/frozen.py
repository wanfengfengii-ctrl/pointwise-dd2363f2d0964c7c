from dataclasses import dataclass
from fractions import Fraction

from observations.revisions import RevisionRef


@dataclass(frozen=True, slots=True)
class ClockLogBinding:
    revision: RevisionRef
    device_log: tuple[tuple[int, str], ...]
    reference_log: tuple[tuple[int, str], ...]
    rate_range: tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class ClockRegistration:
    clock_id: str
    binding: ClockLogBinding
    rate: Fraction
    offset: Fraction
    matches: tuple[tuple[int, int, str], ...]


@dataclass(frozen=True, slots=True)
class ClockReportBinding:
    clock_id: str
    curve_id: str
    target: str
    window: tuple[int, int]
