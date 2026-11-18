from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from calibration.curves import Knot
from observations.series import Sample
from processing.integrals import integrate_interval
from processing.intervals import DirectInterval


@dataclass(frozen=True, slots=True)
class Contribution:
    start: Fraction
    end: Fraction
    samples: tuple[Sample, Sample]
    curve_id: str
    direction: str
    segment_index: int
    knots: tuple[Knot, Knot]
    integral: Fraction


@dataclass(frozen=True, slots=True)
class ContributionLedger:
    contributions: tuple[Contribution, ...]
    coverage: Fraction
    total: Fraction


def make_contribution(interval: DirectInterval) -> Contribution:
    return Contribution(
        interval.start, interval.end, interval.samples, interval.curve_id, interval.direction,
        interval.segment.index, (interval.segment.left, interval.segment.right),
        integrate_interval(interval),
    )


def close_ledger(items: Iterable[Contribution],
                 intersection: tuple[int, int] | None) -> ContributionLedger:
    contributions = tuple(items)
    coverage = Fraction(0)
    total = Fraction(0)
    if intersection is None:
        if contributions:
            raise ValueError('empty observation coverage cannot have contributions')
        return ContributionLedger(contributions, coverage, total)
    cursor, end = intersection
    for item in contributions:
        if item.start != cursor or item.end <= item.start or item.end > end:
            raise ValueError('contributions must cover the observation intersection in order')
        coverage += item.end - item.start
        total += item.integral
        cursor = item.end
    if cursor != end:
        raise ValueError('contributions end before the observation intersection')
    return ContributionLedger(contributions, coverage, total)
