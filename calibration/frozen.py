from dataclasses import dataclass

from calibration.curves import CurveSegment, Knot, normalize_knots
from quantities import require_name


@dataclass(frozen=True, slots=True)
class DirectCurve:
    curve_id: str
    source: str
    target: str
    knots: tuple[Knot, ...]


@dataclass(frozen=True, slots=True)
class OrientedCurve:
    curve_id: str
    source: str
    target: str
    direction: str
    segments: tuple[CurveSegment, ...]


def freeze_curve(curve_id: str, source: str, target: str, knots: object) -> DirectCurve:
    require_name(curve_id, 'curve ID')
    require_name(source, 'source scale')
    require_name(target, 'target scale')
    if source == target:
        raise ValueError('source and target scales must differ')
    return DirectCurve(curve_id, source, target, normalize_knots(knots))
