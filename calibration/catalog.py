import sqlite3

from calibration.frozen import DirectCurve, freeze_curve
from calibration.records import load_curve, store_curve
from quantities import require_name


def register_curve(connection: sqlite3.Connection, curve_id: str, source: str,
                   target: str, knots: object) -> DirectCurve:
    proposed = freeze_curve(curve_id, source, target, knots)
    connection.execute('BEGIN IMMEDIATE')
    with connection:
        existing = load_curve(connection, curve_id)
        if existing is None:
            store_curve(connection, proposed)
            return proposed
        if existing != proposed:
            raise ValueError(f'curve {curve_id!r} has a different fixed binding')
        return existing


def get_curve(connection: sqlite3.Connection, curve_id: str) -> DirectCurve:
    require_name(curve_id, 'curve ID')
    curve = load_curve(connection, curve_id)
    if curve is None:
        raise KeyError(curve_id)
    return curve
