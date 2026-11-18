from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction

from quantities import exact_fraction, iter_pairs

Knot = tuple[Fraction, Fraction]


@dataclass(frozen=True, slots=True)
class CurveSegment:
    index: int
    left: Knot
    right: Knot
    input_axis: int = 0

    @property
    def input_start(self) -> Fraction:
        return self.left[self.input_axis]

    @property
    def input_end(self) -> Fraction:
        return self.right[self.input_axis]

    @property
    def output_start(self) -> Fraction:
        return self.left[1 - self.input_axis]

    @property
    def output_end(self) -> Fraction:
        return self.right[1 - self.input_axis]


def normalize_knots(records: object) -> tuple[Knot, ...]:
    knots = tuple(
        (exact_fraction(x, 'curve x'), exact_fraction(y, 'curve y'))
        for x, y in iter_pairs(records, 'curve knot')
    )
    if len(knots) < 2 or knots[0] != (0, 0) or knots[-1] != (1, 1):
        raise ValueError('curve must run from (0,0) to (1,1)')
    for left, right in zip(knots, knots[1:]):
        if left[0] >= right[0] or left[1] >= right[1]:
            raise ValueError('both curve axes must be strictly increasing')
    return knots


def build_segments(knots: tuple[Knot, ...]) -> tuple[CurveSegment, ...]:
    return tuple(
        CurveSegment(index, left, right)
        for index, (left, right) in enumerate(zip(knots, knots[1:]))
    )


def locate_segment(segments: tuple[CurveSegment, ...], value: Fraction) -> CurveSegment:
    if not 0 <= value <= 1:
        raise ValueError('calibration input is outside [0,1]')
    index = bisect_right(segments, value, key=lambda segment: segment.input_start) - 1
    return segments[index]


def evaluate_segment(segment: CurveSegment, value: Fraction) -> Fraction:
    relative = (value - segment.input_start) / (segment.input_end - segment.input_start)
    return segment.output_start + relative * (segment.output_end - segment.output_start)
