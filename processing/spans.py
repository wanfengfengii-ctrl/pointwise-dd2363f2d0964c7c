from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from observations.series import Sample
from observations.windows import ObservationWindow


@dataclass(frozen=True, slots=True)
class ClippedSpan:
    start: Fraction
    end: Fraction
    start_reading: Fraction
    end_reading: Fraction
    samples: tuple[Sample, Sample]


def interpolate_reading(first: Sample, last: Sample, time_s: Fraction) -> Fraction:
    proportion = (time_s - first.time_s) / (last.time_s - first.time_s)
    return first.reading + proportion * (last.reading - first.reading)


def iter_clipped_spans(window: ObservationWindow) -> Iterator[ClippedSpan]:
    if window.intersection is None:
        return
    left, right = window.intersection
    for first, last in window.pairs:
        start = Fraction(max(left, first.time_s))
        end = Fraction(min(right, last.time_s))
        yield ClippedSpan(
            start, end, interpolate_reading(first, last, start),
            interpolate_reading(first, last, end), (first, last),
        )
