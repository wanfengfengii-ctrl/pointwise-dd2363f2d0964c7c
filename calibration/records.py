import sqlite3
from fractions import Fraction

from calibration.frozen import DirectCurve


def ensure_curve_schema(connection: sqlite3.Connection) -> None:
    connection.execute('''
        CREATE TABLE IF NOT EXISTS curves (
            curve_id TEXT PRIMARY KEY NOT NULL,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            CHECK (source <> target)
        )
    ''')
    connection.execute('''
        CREATE TABLE IF NOT EXISTS curve_knots (
            curve_id TEXT NOT NULL REFERENCES curves(curve_id),
            ordinal INTEGER NOT NULL,
            x TEXT NOT NULL,
            y TEXT NOT NULL,
            PRIMARY KEY (curve_id, ordinal)
        )
    ''')


def load_curve(connection: sqlite3.Connection, curve_id: str) -> DirectCurve | None:
    header = connection.execute(
        'SELECT source, target FROM curves WHERE curve_id = ?', (curve_id,)
    ).fetchone()
    if header is None:
        return None
    knots = tuple(
        (Fraction(x), Fraction(y))
        for x, y in connection.execute(
            'SELECT x, y FROM curve_knots WHERE curve_id = ? ORDER BY ordinal', (curve_id,)
        )
    )
    return DirectCurve(curve_id, header[0], header[1], knots)


def store_curve(connection: sqlite3.Connection, curve: DirectCurve) -> None:
    connection.execute(
        'INSERT INTO curves (curve_id, source, target) VALUES (?, ?, ?)',
        (curve.curve_id, curve.source, curve.target),
    )
    connection.executemany(
        'INSERT INTO curve_knots (curve_id, ordinal, x, y) VALUES (?, ?, ?, ?)',
        ((curve.curve_id, i, str(x), str(y)) for i, (x, y) in enumerate(curve.knots)),
    )
