from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from calibration.curves import CurveSegment, locate_segment
from calibration.frozen import OrientedCurve
from observations.series import Sample
from processing.spans import ClippedSpan


@dataclass(frozen=True, slots=True)
class DirectInterval:
    start: Fraction
    end: Fraction
    start_reading: Fraction
    end_reading: Fraction
    samples: tuple[Sample, Sample]
    curve_id: str
    direction: str
    segment: CurveSegment


def split_direct_span(span: ClippedSpan, curve: OrientedCurve) -> Iterator[DirectInterval]:
    cuts = [(span.start, span.start_reading), (span.end, span.end_reading)]
    change = span.end_reading - span.start_reading
    if change:
        low, high = sorted((span.start_reading, span.end_reading))
        duration = span.end - span.start
        for segment in curve.segments[1:]:
            knot = segment.input_start
            if low < knot < high:
                time = span.start + duration * (knot - span.start_reading) / change
                cuts.append((time, knot))
        cuts.sort()
    for (left, x0), (right, x1) in zip(cuts, cuts[1:]):
        segment = locate_segment(curve.segments, (x0 + x1) / 2)
        yield DirectInterval(
            left, right, x0, x1, span.samples, curve.curve_id, curve.direction, segment,
        )
