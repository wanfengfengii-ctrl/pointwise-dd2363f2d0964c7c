from dataclasses import replace

from calibration.curves import CurveSegment, build_segments
from calibration.frozen import DirectCurve, OrientedCurve


def invert_segments(segments: tuple[CurveSegment, ...]) -> tuple[CurveSegment, ...]:
    return tuple(replace(segment, input_axis=1 - segment.input_axis) for segment in segments)


def orient_curve(curve: DirectCurve, source: str, target: str) -> OrientedCurve:
    if (source, target) == (curve.source, curve.target):
        return OrientedCurve(curve.curve_id, source, target, 'forward', build_segments(curve.knots))
    if (source, target) == (curve.target, curve.source):
        segments = invert_segments(build_segments(curve.knots))
        return OrientedCurve(curve.curve_id, source, target, 'reverse', segments)
    raise ValueError('batch scale and target must select opposite endpoints of the direct curve')
